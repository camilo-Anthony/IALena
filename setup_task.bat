schtasks /create /tn "CheckBattery100" /tr "python.exe C:\Users\hp\Documents\PROYECTOS\JARVIS\scripts\check_battery.py" /sc minute /mo 5 /f
