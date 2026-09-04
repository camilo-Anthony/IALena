import psutil
from plyer import notification

def check_battery():
    battery = psutil.sensors_battery()
    if battery and battery.percent >= 100 and battery.power_plugged:
        notification.notify(
            title="Batería al 100%",
            message="El dispositivo ha alcanzado la carga completa.",
            timeout=10
        )

if __name__ == "__main__":
    check_battery()
