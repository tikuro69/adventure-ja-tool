# adventure-ja-tool

`adventure` 系テキストの日本語化作業を補助するための、個人用の非公式ツールです。

このリポジトリには元作品そのものやストーリーファイルは含まれていません。  
利用する場合は、各自で正規に入手したファイルを用意してください。

## Features

- インタプリタ経由でテキストを取得
- 不要な表示や制御文字を整形
- 用語集ベースで日本語化のたたき台を出力
- 英文と日本語文を並べて確認可能

## Requirements

- Python 3.10+
- `pexpect`
- `dfrotz` などの Z-machine interpreter

## Install

```bash
pip install -r requirements.txt


```

## Usage
python main.py --story Advent.z5 --interpreter dfrotz


## Files
main.py : メインスクリプト
glossary.json : 単語置換用の簡易用語集

## Notes
このツールは非公式です
元作品データは含みません
z-machieインタプリタはインストールしてください
出力される日本語は自動整形・半自動翻訳のたたき台です
最終的な翻訳・校正は手動で行ってください