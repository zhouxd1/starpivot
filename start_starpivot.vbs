' StarPivot backend launcher - survives terminal recycling
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

spDir = "C:\Users\love_\starpivot"
pyExe = spDir & "\.venv\Scripts\python.exe"
logFile = spDir & "\starpivot_run.log"

' skip if port 8899 already listening
Set exec = shell.Exec("cmd /c netstat -ano | findstr :8899 | findstr LISTENING")
out = exec.StdOut.ReadAll()
If Len(Replace(out, vbCrLf, "")) > 2 Then
  WScript.Quit
End If

shell.CurrentDirectory = spDir
shell.Run """" & pyExe & """ main.py >> """ & logFile & """ 2>&1", 0, False
