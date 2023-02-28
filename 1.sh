#!/bin/sh

rm *.apk
p4a apk --private ./ --package=org.example.myapp --name "Trainer" --version 0.2 --bootstrap=sdl2 --arch arm64-v8a --arch armeabi-v7a --requirements=python3,kivy,xmltodict,youtube-transcript-api --permission android.permission.WRITE_EXTERNAL_STORAGE --add-resource main.db
