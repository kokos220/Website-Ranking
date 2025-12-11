import sys
import re

from graphviz import Source
import networkx as nx

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QStackedWidget
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QGuiApplication


# ---------- ЗАВАНТАЖЕННЯ ГРАФУ З menu.dot ----------

def load_graph(path="menu.dot"):
    """
    Завантажуємо орієнтований граф з menu.dot.
    Повертаємо:
      G            - nx.DiGraph
      label_to_id  - мапа "текстова назва страви" -> id вершини (A, B, ...)
      id_to_label  - мапа "id вершини" -> "текстова назва страви"
    """
    src = Source.from_file(path)
    dot = src.source

    G = nx.DiGraph()
    id_to_label = {}
    label_to_id = {}

    for line in dot.splitlines():
        line = line.strip().rstrip(";")
        if not line or line.startswith("//") or line.startswith("digraph") or line in ("{", "}"):
            continue

        # Вершини: A [label="Чізбургер"];
        node_match = re.match(r'(\w+)\s+\[label="(.+)"\]', line)
        if node_match:
            node_id, label = node_match.groups()
            G.add_node(node_id)
            id_to_label[node_id] = label
            label_to_id[label] = node_id
            continue

        # Ребра: A -> B [label="..."];
        if "->" in line:
            parts = line.split("->")
            if len(parts) >= 2:
                start = parts[0].strip()
                end = parts[1].split("[")[0].strip()
                G.add_edge(start, end)

    return G, label_to_id, id_to_label


# ---------- ЕКРАН №1: СТАРТ ----------

class StartPage(QWidget):
    """Перший екран з кнопкою 'Розпочати'."""
    start_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Ласкаво просимо до меню продуктів!")
        title.setStyleSheet("font-size: 18px;")
        title.setAlignment(Qt.AlignCenter)

        btn = QPushButton("Розпочати роботу")
        btn.setFixedHeight(40)
        btn.clicked.connect(self.start_clicked.emit)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(btn, alignment=Qt.AlignCenter)
        layout.addStretch()


# ---------- ЕКРАН №2: ВИБІР СТРАВ ----------

class MenuPage(QWidget):
    """Другий екран: список продуктів з чекбоксами + кнопка 'Далі'."""
    next_clicked = pyqtSignal()

    def __init__(self, products):
        """
        products: список назв страв (labels з dot-файлу)
        """
        super().__init__()

        self.products = products
        self.rows = []  # зберігаємо (name, checkbox)

        main_layout = QVBoxLayout(self)

        # Список: назва страви зліва, чекбокс справа
        for name in self.products:
            row_layout = QHBoxLayout()

            label = QLabel(name)
            checkbox = QCheckBox()

            row_layout.addWidget(label)
            row_layout.addStretch()
            row_layout.addWidget(checkbox)

            main_layout.addLayout(row_layout)
            self.rows.append((name, checkbox))

        main_layout.addStretch()

        # Кнопка "Перейти далі" справа знизу
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        next_btn = QPushButton("Перейти далі")
        next_btn.clicked.connect(self.next_clicked.emit)
        bottom_layout.addWidget(next_btn)

        main_layout.addLayout(bottom_layout)

    def get_selected_products(self):
        """Повертає список назв обраних продуктів."""
        selected = []
        for name, checkbox in self.rows:
            if checkbox.isChecked():
                selected.append(name)
        return selected


# ---------- ЕКРАН №3: РЕКОМЕНДАЦІЇ ----------

class RecommendationsPage(QWidget):
    """
    Третій екран:
      - показує, що користувач вибрав;
      - якщо 1 страва: рекомендує всі, на які з неї є пряме ребро;
      - якщо кілька страв: шукає найближчі спільні вершини;
      - додатково показує глобальний топ продуктів за PageRank.
    """
    def __init__(self, graph: nx.DiGraph, label_to_id: dict, id_to_label: dict):
        super().__init__()

        self.G = graph
        self.label_to_id = label_to_id    # "Чізбургер" -> "A"
        self.id_to_label = id_to_label    # "A" -> "Чізбургер"

        # Глобальний PageRank для всього меню
        self.global_pr = nx.pagerank(self.G, alpha=0.85)

        main_layout = QVBoxLayout(self)

        self.title = QLabel("Рекомендації на основі графу меню")
        self.title.setStyleSheet("font-size: 18px;")

        main_layout.addWidget(self.title)

        self.selected_label = QLabel("")
        self.selected_label.setWordWrap(True)
        main_layout.addWidget(self.selected_label)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        main_layout.addWidget(self.result_label)

        main_layout.addStretch()

    def _build_global_pagerank_text(self, top_k: int = 5) -> str:
        """Формує текст із найпопулярнішими продуктами за глобальним PageRank."""
        ranked = sorted(self.global_pr.items(), key=lambda x: x[1], reverse=True)
        lines = []
        for node_id, score in ranked[:top_k]:
            label = self.id_to_label.get(node_id, node_id)
            lines.append(f"• {label} (PR: {score:.3f})")

        if not lines:
            return "Немає даних PageRank."

        return "Найпопулярніші продукти за PageRank:\n" + "\n".join(lines)

    def set_products(self, products):
        """
        products: список назв страв, які обрав користувач.
        Тут же рахуємо рекомендації згідно з твоїм правилом + додаємо глобальний PageRank.
        """
        if not products:
            self.selected_label.setText("Ви не вибрали жодного продукту 😅")
            self.result_label.setText(self._build_global_pagerank_text())
            return

        # Показуємо, що вибрав користувач
        selected_text = "Ви вибрали:\n" + "\n".join(f"• {p}" for p in products)
        self.selected_label.setText(selected_text)

        # Переводимо назви в id вузлів графа
        selected_ids = []
        for name in products:
            node_id = self.label_to_id.get(name)
            if node_id is not None:
                selected_ids.append(node_id)

        if not selected_ids:
            text = "Не вдалося знайти обрані страви в графі.\n\n"
            text += self._build_global_pagerank_text()
            self.result_label.setText(text)
            return

        # --- ВИПАДОК 1: одна вибрана страва → прямі сусіди ---
        if len(selected_ids) == 1:
            src = selected_ids[0]
            succs = list(self.G.successors(src))

            if not succs:
                text = "Для цієї страви немає прямих рекомендацій.\n\n"
                text += self._build_global_pagerank_text()
                self.result_label.setText(text)
                return

            lines = []
            for node_id in succs:
                label = self.id_to_label.get(node_id, node_id)
                lines.append(f"• {label}")

            text = "Прямі рекомендовані страви (по ребрах з вибраної):\n" + "\n".join(lines)
            text += "\n\n" + self._build_global_pagerank_text()
            self.result_label.setText(text)
            return

        # --- ВИПАДОК 2: кілька вибраних страв → найближчий спільний вузол(ли) ---

        # Рахуємо найкороткі шляхи від кожної вибраної вершини
        distances_per_source = {
            src: nx.single_source_shortest_path_length(self.G, src)
            for src in selected_ids
        }

        reachable_sets = []
        selected_set = set(selected_ids)

        for src, dist_dict in distances_per_source.items():
            reachable = set(dist_dict.keys()) - selected_set
            reachable_sets.append(reachable)

        if not reachable_sets:
            text = "Немає спільних досяжних вершин.\n\n"
            text += self._build_global_pagerank_text()
            self.result_label.setText(text)
            return

        common_nodes = set.intersection(*reachable_sets)

        if common_nodes:
            # Для кожної спільної вершини порахуємо "відстань" –
            # беремо максимум відстаней від усіх вибраних вершин
            scores = {}
            for node in common_nodes:
                dists = []
                for src, dist_dict in distances_per_source.items():
                    if node in dist_dict:
                        dists.append(dist_dict[node])
                    else:
                        dists.append(float("inf"))
                scores[node] = max(dists)

            min_score = min(scores.values())
            best_nodes = [n for n, s in scores.items() if s == min_score]

            lines = []
            for node_id in best_nodes:
                label = self.id_to_label.get(node_id, node_id)
                lines.append(f"• {label} (макс. відстань: {scores[node_id]})")

            text = (
                "Найближчі спільні рекомендовані страви "
                "(мінімальна максимальна відстань від усіх вибраних):\n"
                + "\n".join(lines)
            )
            text += "\n\n" + self._build_global_pagerank_text()
            self.result_label.setText(text)
        else:
            # fallback: якщо спільних немає, показуємо об'єднання прямих сусідів
            neighbours = set()
            for src in selected_ids:
                neighbours.update(self.G.successors(src))
            neighbours -= selected_set

            if not neighbours:
                text = (
                    "Немає спільних досяжних вершин і немає прямих сусідів для рекомендацій.\n\n"
                )
                text += self._build_global_pagerank_text()
                self.result_label.setText(text)
                return

            lines = []
            for node_id in neighbours:
                label = self.id_to_label.get(node_id, node_id)
                lines.append(f"• {label}")

            text = (
                "Не знайдено спільних вершин. Показуємо об'єднання прямих рекомендацій "
                "для кожної вибраної страви:\n" + "\n".join(lines)
            )
            text += "\n\n" + self._build_global_pagerank_text()
            self.result_label.setText(text)


# ---------- ГОЛОВНЕ ВІКНО З QStackedWidget ----------

class MainWindow(QMainWindow):
    def __init__(self, graph, label_to_id, id_to_label):
        super().__init__()

        self.setWindowTitle("Меню продуктів з рекомендаціями по графу")
        self.resize(700, 450)

        self.G = graph
        self.label_to_id = label_to_id
        self.id_to_label = id_to_label

        products = list(self.label_to_id.keys())
        products.sort()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.start_page = StartPage()
        self.menu_page = MenuPage(products)
        self.recommendations_page = RecommendationsPage(self.G, self.label_to_id, self.id_to_label)

        self.stack.addWidget(self.start_page)            # 0
        self.stack.addWidget(self.menu_page)             # 1
        self.stack.addWidget(self.recommendations_page)  # 2

        self.start_page.start_clicked.connect(self.goto_menu)
        self.menu_page.next_clicked.connect(self.goto_recommendations)

        self.center_on_screen()

    def center_on_screen(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def goto_menu(self):
        self.stack.setCurrentWidget(self.menu_page)

    def goto_recommendations(self):
        selected = self.menu_page.get_selected_products()
        self.recommendations_page.set_products(selected)
        self.stack.setCurrentWidget(self.recommendations_page)


# ---------- ТОЧКА ВХОДУ ----------

if __name__ == "__main__":
    G, label_to_id, id_to_label = load_graph("menu.dot")

    app = QApplication(sys.argv)
    window = MainWindow(G, label_to_id, id_to_label)
    window.show()
    sys.exit(app.exec_())
