[app]
title = Stock Screener
package.name = stockscreener
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,yfinance,pandas
orientation = portrait
fullscreen = 1
android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 0