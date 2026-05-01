# tamagotchi-smart-dim-flasher

A local `macOS + CH341A` web flasher for `Tamagotchi Smart` cards.

一个面向 `macOS + CH341A` 的本地 Web 刷卡工具，主要用于 `Tamagotchi Smart` 相关卡片。

## Language

- [中文说明](README.zh-CN.md)
- [English README](README.en.md)

## Quick Summary

- Platform: `macOS`
- Programmer: `CH341A`
- Main target: `Tamagotchi Smart` `DiM / TamaSma / BIM` cards
- Backend: `flashrom`
- UI: local `Flask` web interface

## Notes

- This project is primarily organized and tested around `Tamagotchi Smart`.
- Similar `Digimon` cards may also work in theory, but I have not verified them on real hardware.
- Card images and firmware resources are not bundled in this repository. Please obtain them yourself, for example from [Internet Archive](https://archive.org/), and make sure your use is lawful.

## License

This repository is licensed under `GNU GPL v3.0`.

- When redistributing the original or a modified version, you must keep the original author attribution, copyright notice, and license text.
- If you distribute a modified version, you must also provide the corresponding source code under `GPL-3.0`.

Copyright (C) 2026 `xiyu`
