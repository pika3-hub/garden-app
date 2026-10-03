# AI メモ下書き（作物・品種フォーム）

作物・品種フォームのメモ欄で、Claude API による下書き生成を行う部品。

## 部品

| ファイル | 役割 |
|---|---|
| `app/templates/_ai_notes_button.html` | メモ欄ラベル横のボタン。`ai_available` が false なら無効化＋ツールチップ＋設定画面リンク |
| `app/templates/_ai_notes_modal.html` | 下書きモーダル（Webで調べる・目安表示・生成・結果テキストエリア・置き換え／追記／破棄） |
| `app/static/js/ai-notes.js` | 入力チェック、`POST /settings/ai/notes-draft` 呼び出し、反映 |

## 組み込み方

`{% block content %}` 内で `ai_mode` を set してからボタンとモーダルを include し、`extra_js` で JS を読み込む。

```html
{% set ai_mode = 'crop' %}   {# 品種フォームは 'variety' #}
{% include '_ai_notes_button.html' %}
...
{% include '_ai_notes_modal.html' %}
...
<script src="{{ url_for('static', filename='js/ai-notes.js') }}"></script>
```

JS が参照する既存要素 ID: `notes`, `name`, `crop_type`（作物）、`crop_id_hidden` / `selected-crop-display` / `crop-select-error`（品種）。

## 挙動のルール

- ボタンは APIキー未設定時のみ無効。名前が空などの入力不備は押下時に該当欄を赤枠にして知らせる（無効化しない）
- Webで調べるの初期値: 品種 ON、作物 OFF。目安は `ai_model_info.estimate_on/off`
- 生成中にモーダルを閉じるとリクエストを中断し、古い応答は表示しない
- 反映はフォームのテキストエリアまで。DB 保存はフォームの保存ボタン
- モーダル内アラートは `alert-permanent` 必須（`main.js` が通常の `.alert` を自動で閉じるため）
- 動的な文言は `textContent` で設定する
