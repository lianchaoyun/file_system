Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\project\yun\ai"
WshShell.Run ".venv\Scripts\pythonw.exe -m src.panel", 0, False
Set WshShell = Nothing
