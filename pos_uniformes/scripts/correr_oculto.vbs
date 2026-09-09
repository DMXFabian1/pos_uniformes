' Lanza un .bat de esta misma carpeta SIN mostrar la ventana negra.
' Lo usan las tareas de Windows (vigias cada 5 min) para no interrumpir
' a nadie con un parpadeo de consola.
'   Uso: wscript.exe "...\scripts\correr_oculto.vbs" servidor_pwa_vigia.bat [args]
Option Explicit
Dim sh, fso, carpeta, cmd, i
If WScript.Arguments.Count = 0 Then WScript.Quit 1
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = """" & carpeta & "\" & WScript.Arguments(0) & """"
For i = 1 To WScript.Arguments.Count - 1
  cmd = cmd & " " & WScript.Arguments(i)
Next
sh.Run cmd, 0, False
