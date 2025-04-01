import argostranslate.package
import argostranslate.translate

package_path = "/home/backtalk/Team-4-BACKTALK/src/translate-en_de-1_0.argosmodel"

try:
    argostranslate.package.install_from_path(package_path)
    print("Model installed successfully!")
except Exception as e:
    print(f"Installation failed: {e}")

installed_languages = argostranslate.translate.get_installed_languages()
print("Installed Languages:", [lang.code for lang in installed_languages])
