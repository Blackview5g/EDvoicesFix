# EDvoicesFix 🛠️

[English version below](#english-version)

Программа-прослойка (middleware) на Python, исправляющая критические ошибки парсинга логов в утилите голосовой озвучки **EDvoices** (написанной на Delphi с закрытым исходным кодом).

## Описание проблемы

Оригинальная программа EDvoices падает в ошибку или перестает озвучивать прыжки из-за жестких ограничений встроенного парсера строк:
1. **Ограничение на длину строки:** Лог-событие `FSDJump` в Elite Dangerous бывает слишком длинным (из-за списков фракций, систем конфликтов и т.д.). Парсер Delphi обрезает строку, из-за чего переменные `"FuelUsed"` и `"FuelLevel"` уходят за пределы видимости, вызывая краш.
2. **Чувствительность к форматированию:** EDvoices требует строгого наличия пробелов между переменными и скобками. Сжатый JSON вида `{"event":"FSDJump"}` вызывает ошибку.
3. **Неизвестные фракции:** При обработке значений `"SystemAllegiance"` программа падает, если встречает `"Thargoid"`, `"NONE"`, `"none"` или строку с пробелом `" "`.

## Как работает фикс

Скрипт перехватывает оригинальные логи игры, очищает их от избыточной информации, сохраняет строго необходимую структуру с пробелами и отдаёт EDvoices безопасную урезанную строку.

### Пример трансформации строки лога:
* **Было (вызывает ошибку):** Огромный JSON с массивами фракций `Factions` и конфликтов `Conflicts`, где нужные переменные топлива обрезались парсером.
* **Стало (отлично обрабатывается):**
  `{ "timestamp":"2026-04-27T18:49:51Z", "event":"FSDJump", "SystemAllegiance":"Alliance", "FuelUsed":6.711556, "FuelLevel":121.288445 }`

---

<a name="english-version"></a>
# EDvoicesFix (English) 🛠️

A Python middleware tool that fixes critical log parsing errors in the **EDvoices** voicepack utility (originally written in Delphi with closed source code).

## The Problem

The original EDvoices app crashes or fails to announce jumps due to rigid limitations in its built-in string parser:
1. **String Length Limit:** The `FSDJump` log event in Elite Dangerous can be extremely long (due to massive `Factions` or `Conflicts` arrays). The Delphi parser truncates the line, pushing `"FuelUsed"` and `"FuelLevel"` variables out of range, leading to a crash.
2. **Formatting Sensitivity:** EDvoices strictly requires spaces between JSON variables and brackets. Compressed JSON like `{"event":"FSDJump"}` breaks the parser.
3. **Unsupported Allegiances:** The parser crashes on unexpected `"SystemAllegiance"` values such as `"Thargoid"`, `"NONE"`, `"none"`, or a space `" "`.

## How It Works

The Python script intercepts the original game logs, strips out redundant heavy data, retains the strict spacing format required by Delphi, and feeds EDvoices a safe, compact log line.

### Log Transformation Example:
* **Before (Crashes):** A huge JSON string filled with faction data where fuel variables get cut off.
* **After (Works Perfectly):**
  `{ "timestamp":"2026-04-27T18:49:51Z", "event":"FSDJump", "SystemAllegiance":"Alliance", "FuelUsed":6.711556, "FuelLevel":121.288445 }`

  **Дисклеймер / Disclaimer:**
*   Данная программа является независимым фанатским проектом. Она никак не связана с Frontier Developments plc, не поддерживается ими, а все права на Elite Dangerous принадлежат Frontier Developments.
*   Программа EDvoicesFix создана исключительно для исправления ошибок взаимодействия и распространяется «как есть» (as is). Автор не связан с разработчиками оригинальной утилиты EDvoices.exe. 
*   Используйте на свой страх и риск. Автор не несет ответственности за возможные сбои в работе стороннего ПО, утерянные внутриигровые данные или Анаконду, сгоревшую в лучах белой карликовой звезды.

## License / Лицензия

This project is licensed under the **MIT License** - see the `LICENSE` file for details.
