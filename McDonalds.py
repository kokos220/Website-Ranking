from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QVBoxLayout
from PyQt5.QtGui import QGuiApplication
import networkx as nx
from graphviz import Source
import re
import sys


def load_graph(path="menu.dot"):
    src = Source.from_file(path)
    dot = src.source

    G = nx.DiGraph()
    label_map = {}
    reverse_map = {}

    for line in dot.splitlines():
        line = line.strip().rstrip(";")

        node_match = re.match(r'(\w+)\s+\[label="(.+)"\]', line)
        if node_match:
            node, label = node_match.groups()
            label_map[label.lower()] = node
            reverse_map[node] = label
            G.add_node(node)

        if "->" in line:
            parts = line.split("->")
            if len(parts) >= 2:
                a = parts[0].strip()
                b = parts[1].split("[")[0].strip()   
                G.add_edge(a, b)

    return G, label_map, reverse_map


app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle("Меню-рекомендації")
window.resize(500, 250)

label = QLabel("Введи позицію з меню:")
input_field = QLineEdit()

G, labels, reverse = load_graph("menu.dot")

result = QLabel("")


def show_recommendations(text):
    text = text.lower().strip()

    if text == "":
        result.setText("")
        return
    text = text.lower().strip()

    candidates = [key for key in labels.keys() if text in key]

    if not candidates:
        result.setText("Не знайдено у графі.")
        return

    found = candidates[0]
    node = labels[found]
    recs = list(G.successors(node))

    if recs:
        out = f"Знайдено: {found.capitalize()}\n\nРекомендації:\n"
        for r in recs:
            readable = reverse.get(r, r)
            out += f" • {readable}\n"
    else:
        out = "Немає рекомендацій."

    result.setText(out)


input_field.textChanged.connect(show_recommendations)

layout = QVBoxLayout()
layout.addWidget(label)
layout.addWidget(input_field)
layout.addWidget(result)
window.setLayout(layout)

screen = QGuiApplication.primaryScreen().geometry()
window.move((screen.width()-window.width())//2, (screen.height()-window.height())//2)

window.show()
app.exec()

