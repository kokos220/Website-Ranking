from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QVBoxLayout
from PyQt5.QtGui import QGuiApplication
import sys

app = QApplication(sys.argv)

# ----- Створення вікна -----
window = QWidget()
window.setWindowTitle("My App")
window.resize(400, 200)

# ----- Елементи інтерфейсу -----
label = QLabel("Введи текст:")
input_field = QLineEdit()

# Зміна тексту в Label при вводі
input_field.textChanged.connect(label.setText)

# ----- Вертикальний Layout -----
layout = QVBoxLayout()
layout.addWidget(input_field)
layout.addWidget(label)
window.setLayout(layout)

# ----- Центрування вікна -----
screen = QGuiApplication.primaryScreen().geometry()
x = (screen.width() - window.width()) // 2
y = (screen.height() - window.height()) // 2
window.move(x, y)

# ----- Запуск -----
window.show()
app.exec()
