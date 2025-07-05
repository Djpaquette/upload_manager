# This file is used to configure the build process of your Kivy application.

# name of the application
[app]
title = Upload Manager
package.name = uploadmanager
package.domain = org.example
source.dir = .

#kivy version to use.
kivy_version = 2.3.1

#files to be included in apk file.
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,plyer,requests,msal

#(str) image of loading screen.
presplash.filename = %(source.dir)s/data/presplash.png

#(str) Application icon
icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

#(bool) Whether the application should be fullscreen or not
fullscreen = 0

#(str) Android logcat filters to use.
android.logcat_filters = *:S python:D

#(bool) android logcat only display log for activitys pid.
#android.logcat_pid_only = false

#(str) python-for-android branch to use, defaults to master
p4a.branch = develop
#p4a.branch = master



[buildozer]
log_level = 2
warn_on_root = 1
android.target = 33
# Add any other permissions your app needs

# Android permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

[buildozer]
log_level = 2
warn_on_root = 1
