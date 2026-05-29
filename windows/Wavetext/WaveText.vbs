Dim shell, dir
Set shell = CreateObject("WScript.Shell")
dir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

If Dir(dir & ".venv\Scripts\python.exe") = "" Then
    ' Primeira vez: roda o instalador com terminal visivel
    shell.Run "cmd /c """ & dir & "WaveText.bat""", 1, True
Else
    ' Ja instalado: abre sem terminal
    shell.Run "cmd /c cd /d """ & dir & """ && .venv\Scripts\python.exe main.py", 0, False
End If
