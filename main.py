import os
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
import msal
import threading
from kivy.clock import Clock
from kivy.utils import platform
import webbrowser
from kivy.uix.screenmanager import ScreenManager, Screen

# Disable Kivy multitouch simulator (red dot on right-click) on desktop
from kivy.config import Config
if platform in ("win", "linux", "macosx"):
    Config.set('input', 'mouse', 'mouse,disable_multitouch')

# Android permissions
if platform == "android":
    try:
        from android.permissions import request_permissions, Permission  # type: ignore
    except ImportError:
        request_permissions = None
        Permission = None
else:
    request_permissions = None
    Permission = None

# Use plyer conditionally for mobile filechooser, camera, and browser
try:
    from plyer import filechooser
except ImportError:
    filechooser = None

try:
    from plyer import camera
except ImportError:
    camera = None

# Tkinter fallback for desktop file dialog
import sys
if sys.platform in ("win32", "darwin", "linux"):
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        tk = None
        filedialog = None
else:
    tk = None
    filedialog = None

Builder.load_file('construction.kv')

CLIENT_ID = "f068e903-fd03-4773-bc4e-d38789d70cd2"
TENANT_ID = "82d62937-b5d0-47b9-8daf-b2b1b8f52c03"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
# --- PLATFORM-SPECIFIC SCOPES FIX FOR MSAL ---
# Remove "offline_access" from SCOPES for device code flow (desktop/mobile)
SCOPES = [
    "User.Read",
    "Files.ReadWrite.All"
]
REDIRECT_URI = f"msal{CLIENT_ID}://auth"

class MainScreen(BoxLayout):
    onedrive_folder = "UploadFolder"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.access_token = None
        self.msal_app = msal.PublicClientApplication(
            CLIENT_ID, authority=AUTHORITY
        )
        self.selected_file_paths = []
        self.remote_ip = ""
        self.remote_user = ""
        self.remote_pass = ""
        if platform == "android" and request_permissions is not None and Permission is not None:
            try:
                request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.CAMERA])
            except Exception as e:
                print("Permission request failed:", e)

    def on_folder_select(self, folder_name):
        if folder_name:
            self.onedrive_folder = folder_name
            try:
                self.ids.status_label.text = f"Upload folder set to: {folder_name}"
            except Exception:
                print(f"Upload folder set to: {folder_name}")

    def authenticate(self):
        def do_authenticate():
            accounts = self.msal_app.get_accounts()
            if accounts:
                result = self.msal_app.acquire_token_silent(SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    Clock.schedule_once(lambda dt: self._on_auth_success(result["access_token"]))
                else:
                    Clock.schedule_once(lambda dt: self._on_auth_failed("Silent token acquisition failed."))
            else:
                flow = self.msal_app.initiate_device_flow(scopes=SCOPES)
                if "user_code" not in flow:
                    Clock.schedule_once(lambda dt: self._on_auth_failed("Failed to create device flow. Check app registration."))
                    return
                Clock.schedule_once(lambda dt: self._on_device_code(flow['verification_uri'], flow['user_code']))
                try:
                    webbrowser.open(flow['verification_uri'])
                except Exception:
                    pass
                result = self.msal_app.acquire_token_by_device_flow(flow)
                if result and "access_token" in result:
                    Clock.schedule_once(lambda dt: self._on_auth_success(result["access_token"]))
                else:
                    error_msg = result.get("error_description", "Authentication failed.") if isinstance(result, dict) else "Authentication failed."
                    Clock.schedule_once(lambda dt: self._on_auth_failed(error_msg))
        threading.Thread(target=do_authenticate, daemon=True).start()

    def _on_device_code(self, url, code):
        try:
            self.ids.status_label.text = f"Go to {url} and enter code: {code}"
        except Exception:
            print(f"Go to {url} and enter code: {code}")

    def _on_auth_success(self, token):
        self.access_token = token
        try:
            self.ids.status_label.text = "Authenticated with Microsoft Graph."
        except Exception:
            print("Authenticated with Microsoft Graph.")
        if hasattr(self, '_pending_upload') and self._pending_upload:
            self._pending_upload = False
            self.upload_media(None)

    def _on_auth_failed(self, msg):
        try:
            self.ids.status_label.text = f"Authentication failed: {msg}"
        except Exception:
            print(f"Authentication failed: {msg}")

    def pick_file(self, instance=None):
        print("pick_file called")  # Debug
        """
        Allow user to pick multiple image or video files on all platforms.
        """
        def on_selection(chosen_files):
            if chosen_files:
                # On Android/iOS, plyer returns a list of file paths (strings)
                # On desktop, Tkinter returns a tuple of file paths (strings)
                self.selected_file_paths = list(chosen_files)
                previewed = False
                for file_path in self.selected_file_paths:
                    if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".tiff", ".heif", ".gif")):
                        try:
                            self.ids.preview.source = file_path
                            self.ids.preview.reload()
                        except Exception:
                            pass
                        previewed = True
                        break
                if not previewed:
                    try:
                        self.ids.preview.source = ""
                    except Exception:
                        pass
                try:
                    self.ids.status_label.text = (
                        f"Selected: {len(self.selected_file_paths)} file(s): " +
                        ", ".join([os.path.basename(f) for f in self.selected_file_paths])
                    )
                except Exception:
                    print(f"Selected: {len(self.selected_file_paths)} file(s): " +
                          ", ".join([os.path.basename(f) for f in self.selected_file_paths]))
            else:
                self.selected_file_paths = []
                try:
                    self.ids.status_label.text = "No file selected."
                except Exception:
                    print("No file selected.")

        # --- DESKTOP (Windows/Linux/macOS) ---
        if platform in ("win", "linux", "macosx") and tk is not None and filedialog is not None:
            try:
                root = tk.Tk()
                root.withdraw()
                filetypes = [
                    ("Image and Video files", "*.jpg *.jpeg *.png *.tiff *.heif *.gif *.mp4 *.mov *.avi"),
                    ("All files", "*.*")
                ]
                file_paths = filedialog.askopenfilenames(
                    title="Select image or video files",
                    filetypes=filetypes
                )
                root.destroy()
                on_selection(file_paths)
                return
            except Exception as e:
                try:
                    self.ids.status_label.text = f"File dialog error: {e}"
                except Exception:
                    print("File dialog error:", e)

        # --- ANDROID/iOS (plyer) ---
        if filechooser is not None and hasattr(filechooser, "open_file") and callable(filechooser.open_file):
            try:
                filechooser.open_file(
                    title="Select image or video files",
                    filters=[("*.jpg;*.jpeg;*.png;*.tiff;*.heif;*.gif;*.mp4;*.mov;*.avi",)],
                    multiple=True,
                    on_selection=on_selection
                )
                return
            except Exception as e:
                try:
                    self.ids.status_label.text = f"File chooser error: {e}"
                except Exception:
                    print("File chooser error:", e)

        self.selected_file_paths = []
        try:
            self.ids.status_label.text = "File chooser not available on this platform."
        except Exception:
            print("File chooser not available on this platform.")
        on_selection([])

    def upload_media(self, instance):
        """
        Upload the selected media files to OneDrive and update an Excel file.
        """
        if not self.access_token:
            self._pending_upload = True
            self.authenticate()
            return

        try:
            description = self.ids.description_input.text
        except Exception:
            description = ""
        uploads = []
        # Use the new selected_file_paths list
        if hasattr(self, 'selected_file_paths') and self.selected_file_paths:
            uploads = [f for f in self.selected_file_paths if os.path.exists(f)]

        if not uploads:
            try:
                self.ids.status_label.text = "No media available to upload."
            except Exception:
                print("No media available to upload.")
            return

        access_token = self.access_token
        onedrive_folder = self.onedrive_folder

        success_count = 0
        for file_path in uploads:
            if self._upload_to_onedrive(file_path, description, access_token, onedrive_folder):
                success_count += 1

        try:
            self.ids.status_label.text = f"Uploaded {success_count} file(s) to OneDrive and updated Excel records."
        except Exception:
            print(f"Uploaded {success_count} file(s) to OneDrive and updated Excel records.")

    def _upload_to_onedrive(self, file_path, description, access_token, onedrive_folder):
        """
        Upload a file to OneDrive using Microsoft Graph API and update the Excel report.
        Returns True if upload and Excel update were successful.
        """
        filename = os.path.basename(file_path)
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_folder}/{filename}:/content"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream"
        }
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            response = requests.put(url, headers=headers, data=file_data)
            if response.ok:
                print(f"Upload of {filename} successful.")
                # Determine file type by checking the extension.
                if filename.lower().endswith((".jpg", ".jpeg", ".png", ".tiff", ".heif", ".gif")):
                    file_type = "Image"
                elif filename.lower().endswith((".mp4", ".mov", ".avi")):
                    file_type = "Video"
                else:
                    file_type = "Unknown"
                # Update the Excel record after a successful upload.
                self._update_excel_record(filename, file_type, description, access_token, onedrive_folder)
                return True
            else:
                print(f"Upload failed for {filename}: {response.text}")
                return False
        except Exception as e:
            print("Exception during upload:", e)
            return False

    def _update_excel_record(self, file_name, file_type, description, access_token, onedrive_folder):
        """
        Update an Excel file (UploadRecords.xlsx) stored in OneDrive.
        The Excel file must include a table named "Table1" with columns for:
        File Name, File Type, Description, and Upload Time.
        """
        excel_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_folder}/UploadRecords.xlsx:/workbook/tables/Table1/rows/add"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        upload_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        data = {"values": [[file_name, file_type, description, upload_time]]}
        try:
            response = requests.post(excel_url, headers=headers, json=data)
            if response.ok:
                print(f"Excel updated for {file_name} successfully.")
            else:
                print(f"Error updating Excel for {file_name}: {response.text}")
        except Exception as e:
            print("Exception during Excel update:", e)

class HomeScreen(Screen):
    def pick_file(self, instance):
        # Find the MainScreen child and call its pick_file method
        for child in self.children:
            if isinstance(child, MainScreen):
                return child.pick_file(instance)
        print("MainScreen child not found in HomeScreen")

    def upload_media(self, instance):
        for child in self.children:
            if isinstance(child, MainScreen):
                return child.upload_media(instance)
        print("MainScreen child not found in HomeScreen")

class SettingsScreen(Screen):
    def save_settings(self, onedrive_folder, remote_ip, remote_user, remote_pass):
        app = App.get_running_app()
        if app is not None and hasattr(app, "root") and app.root is not None:
            root_manager = app.root
            home_screen = root_manager.get_screen("home")
            for child in home_screen.children:
                if isinstance(child, MainScreen):
                    child.onedrive_folder = onedrive_folder.strip() if onedrive_folder.strip() else "UploadFolder"
                    child.remote_ip = remote_ip.strip()
                    child.remote_user = remote_user.strip()
                    child.remote_pass = remote_pass.strip()
                    try:
                        self.ids.settings_status_label.text = "Settings saved."
                    except Exception:
                        print("Settings saved.")
                    # Automatically return to home screen after saving
                    app.root.current = "home"
                    break
        else:
            print("Could not save settings: App or root manager is not available.")

class RootScreenManager(ScreenManager):
    pass

class MainApp(App):
    def build(self):
        return RootScreenManager()

if __name__ == '__main__':
    MainApp().run()


