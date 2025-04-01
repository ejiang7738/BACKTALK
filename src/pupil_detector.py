import numpy as np
import time
import psutil
import os
import threading
import subprocess
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
cal_pin = 26

GPIO.setup(cal_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

os.environ["DISPLAY"] = ":0"  # Ensure it connects to the right display
os.environ["XDG_RUNTIME_DIR"] = "/run/user/1000"
os.environ["QT_QPA_PLATFORM"] = "xcb"  # Ensure OpenCV uses the correct Qt backend

env = os.environ.copy()

import cv2

EXIT_FILE = "/tmp/exit_keyboard"

#global variables for blink tracking
blink_threshold = 30
blink_duration = 0.75 #Duration (seconds)
last_blink_time = 0
darkness_value = []
timestamp = []

calibrate_center = None

#Define dictionary to map blink and gaze directions to key press
gaze_to_key = {
    "Up": "w",
    "Down": "s",
    "Left": "a",
    "Right": "d"
}

#Track gaze detection timing
last_gaze_direction = None
gaze_start_time = None
gaze_duration = 0.75 #Seconds

keyboard_running = False
keyboard_start_time = None

def check_keyboard():
    #checks if keyboard is running
    global keyboard_running
    while True:
        keyboard_running = any(
            process.info['cmdline'] and 
            isinstance(process.info['cmdline'], list) and 
            "KeyboardwithTTS.py" in " ".join(process.info['cmdline']) and 
            ("python" in process.info['cmdline'][0] or "python3" in process.info['cmdline'][0])
            for process in psutil.process_iter(attrs=['cmdline'])
        )
        time.sleep(3) #Checks every 3 seconds if keyboard is running

#Starts thread
process_check_thread = threading.Thread(target=check_keyboard, daemon=True)
process_check_thread.start()

def is_keyboard_running():
    global keyboard_running
    return keyboard_running

# Crop the image to maintain a specific aspect ratio (width:height) before resizing.
def crop_to_aspect_ratio(image, width=640, height=480):
    current_height, current_width = image.shape[:2]
    desired_ratio = width / height
    current_ratio = current_width / current_height

    if current_ratio > desired_ratio:
        # Current image is too wide
        new_width = int(desired_ratio * current_height)
        offset = (current_width - new_width) // 2
        cropped_img = image[:, offset:offset + new_width]
    else:
        # Current image is too tall
        new_height = int(current_width / desired_ratio)
        offset = (current_height - new_height) // 2
        cropped_img = image[offset:offset + new_height, :]

    return cv2.resize(cropped_img, (width, height))
    
# Apply thresholding to an image
def apply_binary_threshold(image, darkestPixelValue, addedThreshold):
    threshold = darkestPixelValue + addedThreshold
    _, thresholded_image = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY_INV)
    return thresholded_image

# Finds a square area of dark pixels in the image
def get_darkest_area(image):
    ignoreBounds = 20
    imageSkipSize = 20
    searchArea = 20
    internalSkipSize = 10

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    min_sum = float('inf')
    darkest_point = None

    for y in range(ignoreBounds, gray.shape[0] - ignoreBounds, imageSkipSize):
        for x in range(ignoreBounds, gray.shape[1] - ignoreBounds, imageSkipSize):
            current_sum = 0
            num_pixels = 0
            for dy in range(0, searchArea, internalSkipSize):
                if y + dy >= gray.shape[0]:
                    break
                for dx in range(0, searchArea, internalSkipSize):
                    if x + dx >= gray.shape[1]:
                        break
                    current_sum += gray[y + dy][x + dx]
                    num_pixels += 1

            if current_sum < min_sum and num_pixels > 0:
                min_sum = current_sum
                darkest_point = (x + searchArea // 2, y + searchArea // 2)

    avg_darkness = min_sum / num_pixels if num_pixels > 0 else 0

    #Define eye region (bounding box) for gaze detection
    bounding_box = (
        ignoreBounds, ignoreBounds,
        gray.shape[1] - 2 * ignoreBounds,
        gray.shape[0] - 2 * ignoreBounds
    )

    return darkest_point, avg_darkness, bounding_box
    
# Mask all pixels outside a square defined by center and size
def mask_outside_square(image, center, size):
    x, y = center
    half_size = size // 2

    mask = np.zeros_like(image)
    top_left_x = max(0, x - half_size)
    top_left_y = max(0, y - half_size)
    bottom_right_x = min(image.shape[1], x + half_size)
    bottom_right_y = min(image.shape[0], y + half_size)
    mask[top_left_y:bottom_right_y, top_left_x:top_left_x + size] = 255
    return cv2.bitwise_and(image, mask)
    
# Returns the largest contour that is not extremely long or tall
def filter_contours_by_area_and_return_largest(contours, pixel_thresh, ratio_thresh):
    max_area = 0
    largest_contour = None

    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= pixel_thresh:
            x, y, w, h = cv2.boundingRect(contour)
            length_to_width_ratio = max(w / h, h / w)
            if length_to_width_ratio <= ratio_thresh:
                if area > max_area:
                    max_area = area
                    largest_contour = contour

    return [largest_contour] if largest_contour is not None else []

# Process frames for pupil detection
def process_frames(thresholded_image_medium, frame, gray_frame, darkest_point, debug_mode_on, render_cv_window):
    kernel_size = 5
    kernel = np.ones((kernel_size, kernel_size), np.uint8)

    dilated_image = cv2.dilate(thresholded_image_medium, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    reduced_contours = filter_contours_by_area_and_return_largest(contours, 1000, 3)

    final_rotated_rect = ((0, 0), (0, 0), 0)
    if len(reduced_contours) > 0 and len(reduced_contours[0]) > 5:
        ellipse = cv2.fitEllipse(reduced_contours[0])
        cv2.ellipse(frame, ellipse, (0, 255, 0), 2)
        center_x, center_y = map(int, ellipse[0])
        cv2.circle(frame, (center_x, center_y), 3, (255, 255, 0), -1)
        final_rotated_rect = ellipse

    # Calculate FPS
    current_time = time.time()
    fps = int(1 / (current_time - process_frames.last_time)) if hasattr(process_frames, "last_time") else 0
    process_frames.last_time = current_time

    # Display FPS on the frame
    cv2.putText(frame, f"FPS: {fps}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    frame = cv2.resize(frame, (640, 480))
    cv2.imshow("Frame with Ellipse", frame)

    if render_cv_window:
        cv2.imshow("Best Thresholded Image Contours on Frame", frame)

    return final_rotated_rect
    
# Process a single frame for pupil detection
def process_frame(frame):
    global darkness_values, timestamps, calibrate_center, last_gaze_direction, gaze_start_time, last_blink_time, keyboard_start_time
    start_time = time.time()
    
    frame = crop_to_aspect_ratio(frame)
    #print(f"Time after crop_to_aspect_ratio: {time.time() - start_time:.6f} seconds")
    
    darkest_point, avg_darkness, bounding_box = get_darkest_area(frame)
    #print(f"Time after get_darkest_area: {time.time() - start_time:.6f} seconds")
    
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #print(f"Time after cvtColor to gray: {time.time() - start_time:.6f} seconds")

    darkest_pixel_value = gray_frame[darkest_point[1], darkest_point[0]]
    threshold_image = apply_binary_threshold(gray_frame, darkest_pixel_value, 15)

    #Calibrate when 'c' is pressed
    key = cv2.waitKey(1) & 0xFF

    if key == ord('c') or GPIO.input(cal_pin) == GPIO.LOW:
        calibrate_center = darkest_point
        print("Center Calibrated", calibrate_center)

        keyboard_start_time = time.time()

        if keyboard_running:
            print("Keyboard already running, restarting")
            with open(EXIT_FILE, "w") as f:
                f.write("EXIT")

            time.sleep(1)
        elif not keyboard_running:
            print("Starting keyboard")
        
        with open("/home/backtalk/keyboard_log.txt", "w") as log_file:
            subprocess.Popen(
                ["/bin/bash", "-c", "source /home/backtalk/Team-4-BACKTALK/src/myenv/bin/activate && python3 /home/backtalk/Team-4-BACKTALK/src/KeyboardwithTTS.py"], env=env,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True
            )

    #If no calibration, set default (center is frame center)
    if calibrate_center is None:
        calibrate_center = (frame.shape[1] // 2, frame.shape[0] // 2)

    #Computing the offsets from the calibrated center
    offsetx = darkest_point[0] - calibrate_center[0]
    offsety = darkest_point[1] - calibrate_center[1]
    
    darkest_pixel_value = gray_frame[darkest_point[1], darkest_point[0]]
    thresholded_image_medium = apply_binary_threshold(gray_frame, darkest_pixel_value, 15)
    #print(f"Time after apply_binary_threshold: {time.time() - start_time:.6f} seconds")
    
    thresholded_image_medium = mask_outside_square(thresholded_image_medium, darkest_point, 250)
    #print(f"Time after mask_outside_square: {time.time() - start_time:.6f} seconds")

    #Append darkness value and timestamp
    timestamp.append(time.time())
    darkness_value.append(avg_darkness)

    #Keep only recent values within blink duration)
    while timestamp and timestamp[-1] - timestamp[0] > blink_duration:
        timestamp.pop(0)
        darkness_value.pop(0)

    if keyboard_start_time and (time.time() - keyboard_start_time) < 10:
        cv2.putText(frame, "Calibrated, Keyboard Loading...", (frame.shape[1] // 2 - 150, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
    

    #Check if darkest region has been above threshold
    current_time = time.time()
    if len(darkness_value) > 0 and min(darkness_value) > blink_threshold:
        if current_time - last_blink_time >= blink_duration:
            cv2.putText(frame, "Blink Detected", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            if keyboard_running:
                os.system("sudo ydotool key 28:1 28:0")
                last_blink_time = current_time

    #cv2.putText(frame, "Blink Detected", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame, f"{avg_darkness:.2f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
        #Detect gaze direction
    gaze_direction = "Center"
    if offsetx < -40:
        gaze_direction = "Right"
    elif offsetx > 40:
        gaze_direction ="Left"
    elif offsety < -30:
        gaze_direction = "Up"
    elif offsety > 30:
        gaze_direction = "Down"
    
    
    #Display gaze direction on the frame
    cv2.putText(frame, f"Gaze: {gaze_direction}", (400,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)

    #Check that gaze is held for threshold
    current_time = time.time()
    if gaze_direction != "Center" and keyboard_running and min(darkness_value) < blink_threshold and len(darkness_value) > 0:
        if gaze_direction == last_gaze_direction:
            #If gaze held long enough, trigger key press
            if current_time - gaze_start_time >= gaze_duration:
                if gaze_direction == "Up":
                    os.system("sudo ydotool type -d, --key-delay 200 'w'")
                elif gaze_direction == "Down":
                    os.system("sudo ydotool type -d, --key-delay 200 's'")
                elif gaze_direction == "Right":
                    os.system("sudo ydotool type -d, --key-delay 200 'd'")
                elif gaze_direction == "Left":
                    os.system("sudo ydotool type -d, --key-delay 200 'a'")

                #Reset the timer once a key is pressed
                gaze_start_time = time.time()
                    
        else:
            #Gaze changed, reset timer
            last_gaze_direction = gaze_direction
            gaze_start_time = time.time()
    else:
        #Reset when gaze is centered
        last_gaze_direction = None
        gaze_start_time = time.time()

    result = process_frames(thresholded_image_medium, frame, gray_frame, darkest_point, False, False)
    #print(f"Time after process_frames: {time.time() - start_time:.6f} seconds")
    
    return result

# Process video frames for pupil detection using OpenCV
def process_video_with_opencv():
    cap = cv2.VideoCapture(0)  # Open USB camera (adjust index if needed)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    #cv2.namedWindow("Eye Tracker", cv2.WINDOW_NORMAL)
    #cv2.resizeWindow("Eye Tracker", 800, 600)

    time.sleep(0.5)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame.")
            break

        process_frame(frame)

        # cv2.imshow("Eye Tracker", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    process_video_with_opencv()
