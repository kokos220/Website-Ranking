"""PageRank crawler with PyQt5 GUI (без власних класів)"""

import sys
import re
from urllib.parse import urljoin, urldefrag
from urllib.request import urlopen, Request

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QMessageBox
)

APP = None
WINDOW = None
URL_EDIT = None
DEPTH_EDIT = None
MAX_LINKS = None
START_BUT = None
LOG_TXT = None

def read_file(file_name: str) -> list[str]:
    """
    Зчитує граф з файлу. Кожен рядок: url -> url.
    """
    with open(file_name, 'r', encoding='utf-8') as file:
        file_con = file.readlines()
    return file_con

def create_dictionaries(file_content: list[str]) -> tuple:
    """
    Створює словники з графа.
    """
    vertical_out = {}
    vertical_in = {}
    page_rank = {}
    vertexes = set()
    not_used_vertexes = set()
    for elem in file_content:
        elem = elem.strip()
        if not elem:
            continue
        if '->' not in elem:
            continue
        start_point, end_point = elem.split('->', 1)
        start_point = start_point.strip()
        end_point = end_point.strip()
        if not start_point or not end_point:
            continue
        vertical_out.setdefault(start_point, set()).add(end_point)
        vertical_in.setdefault(end_point, set()).add(start_point)
        vertexes.add(start_point)
        vertexes.add(end_point)
    if not vertexes:
        return vertical_in, vertical_out, {}, vertexes, not_used_vertexes
    page_rank = dict.fromkeys(vertexes, 1 / len(vertexes))
    page_rank = dict(sorted(page_rank.items(), key=lambda x: x[0]))
    return vertical_in, vertical_out, page_rank, vertexes, not_used_vertexes

def get_page_rank(page_rank, out_in_ribs, in_out_ribs, peaks, useless_peaks):
    """
    Знаходить PageRank для вершин графа.
    """
    if not peaks:
        return {}
    all_vertexes_counter = len(peaks)
    previous_pr = page_rank.copy()
    all_peaks = peaks | useless_peaks
    start = True
    no_exit_vert = [vert for vert in all_peaks if vert not in out_in_ribs]
    damping = 0.85
    base = (1 - damping) / all_vertexes_counter
    while start or any(abs(previous_pr[v] - page_rank[v]) > 1e-6 for v in page_rank):
        start = False
        previous_pr = page_rank.copy()
        dangling_sum = sum(previous_pr[v] for v in no_exit_vert)
        for peak in all_peaks:
            coefficients_sum = 0.0
            if peak in in_out_ribs:
                for point in in_out_ribs[peak]:
                    point_rank = previous_pr[point]
                    point_outs = len(out_in_ribs[point])
                    if point_outs:
                        coefficients_sum += point_rank / point_outs
            page_rank[peak] = (base + damping *
                               (coefficients_sum + dangling_sum / all_vertexes_counter))
    page_rank = dict(sorted(page_rank.items(), key=lambda x: x[1], reverse=True))
    return page_rank


def log_message(msg: str):
    """Виводить повідомлення в QTextEdit і оновлює дані."""
    global LOG_TXT
    if LOG_TXT is not None:
        LOG_TXT.append(msg)
        LOG_TXT.moveCursor(LOG_TXT.textCursor().End)
        QApplication.processEvents()

def search_links(start_url: str, max_depth: int, output_path: str, max_links_per_page: int):
    """
    Обходить посилання і записує: url -> url у файл output_path.
    """
    visited = set()
    href_pattern = r'href\s*=\s*["\']([^"\']+)["\']'
    def is_url(url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")
    def get_html(url: str) -> str | None:
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=5) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return None
    with open(output_path, "w", encoding="utf-8") as f_out:
        def write_line(src: str, dst: str):
            f_out.write(f"{src} -> {dst}\n")
        def search(url: str, depth: int):
            if depth > max_depth or url in visited:
                return
            visited.add(url)
            html = get_html(url)
            if html is None:
                return
            next_depth = depth + 1
            stop_recursion = next_depth > max_depth
            links_taken = 0
            for match in re.finditer(href_pattern, html, flags=re.IGNORECASE):
                href = match.group(1).strip()
                if (href.startswith("mailto:") or
                        href.startswith("javascript:") or
                        'css' in href or
                        'json' in href or
                        '.ico' in href or
                        '.svg' in href or
                        '.js' in href or
                        'creativecommons' in href or
                        'png' in href or
                        'jpg' in href):
                    continue
                full_url, _ = urldefrag(urljoin(url, href))
                if not is_url(full_url):
                    continue
                write_line(url, full_url)
                log_message(f"   -> {full_url}")
                links_taken += 1
                if not stop_recursion:
                    search(full_url, next_depth)
                if links_taken >= max_links_per_page:
                    break
        search(start_url, depth=0)

def run_crawler_and_pagerank(url: str, depth: int, max_links: int):
    """
    Запускає crawler, потім читає файл, рахує PageRank і показує топ-10 у таблиці.
    """
    global START_BUT
    try:
        search_links(url, depth, "menu.dot", max_links)
        log_message('')
        log_message('')
        log_message("Обхід завершено. Читаємо файл та рахуємо PageRank...")
        file_content = read_file("menu.dot")
        (vertical_in, vertical_out,
         pagerank, vertexes, not_used_vertexes) = create_dictionaries(file_content)
        if not vertexes:
            log_message("Не знайдено жодного посилання.")
        else:
            page_ranking = get_page_rank(pagerank, vertical_out,
                                         vertical_in, vertexes, not_used_vertexes)
            top10 = list(page_ranking.items())[:10]
            log_message("=== Топ-10 сторінок за PageRank ===")
            for url_res, pr in top10:
                log_message(f"{pr:.6f}  {url_res}")
    except Exception as e:
        QMessageBox.critical(WINDOW, "Помилка", str(e))
    finally:
        if START_BUT is not None:
            START_BUT.setEnabled(True)

def start_crawling():
    """Зчитує дані з полів, перевіряє."""
    global URL_EDIT, DEPTH_EDIT, MAX_LINKS, LOG_TXT, START_BUT
    url = URL_EDIT.text().strip()
    depth_text = DEPTH_EDIT.text().strip()
    max_links_text = MAX_LINKS.text().strip()
    if not url:
        QMessageBox.warning(WINDOW, "Помилка", "Введіть початковий URL.")
        return
    try:
        depth = int(depth_text)
        max_links = int(max_links_text)
        if depth < 0 or max_links <= 0:
            int('s')
    except ValueError:
        QMessageBox.warning(WINDOW,"Помилка", "Глибина та максимальна кількість посилань "
                            "мають бути додатними цілими числами.")
        return
    LOG_TXT.clear()
    START_BUT.setEnabled(False)
    run_crawler_and_pagerank(url, depth, max_links)

def build_gui():
    """
    Створює вікно, всі віджети і підключає сигнали.
    """
    global WINDOW, URL_EDIT, DEPTH_EDIT, MAX_LINKS
    global START_BUT, LOG_TXT
    WINDOW = QWidget()
    WINDOW.setWindowTitle("PageRank Web Crawler")
    WINDOW.resize(900, 600)
    main_layout = QVBoxLayout(WINDOW)
    form_layout = QVBoxLayout()
    url_layout = QHBoxLayout()
    url_label = QLabel("URL для початку:")
    URL_EDIT = QLineEdit()
    URL_EDIT.setPlaceholderText("https://example.com")
    url_layout.addWidget(url_label)
    url_layout.addWidget(URL_EDIT)
    form_layout.addLayout(url_layout)
    depth_layout = QHBoxLayout()
    depth_label = QLabel("Максимальна глибина пошуку:")
    DEPTH_EDIT = QLineEdit()
    DEPTH_EDIT.setPlaceholderText("наприклад, 1 або 2")
    depth_layout.addWidget(depth_label)
    depth_layout.addWidget(DEPTH_EDIT)
    form_layout.addLayout(depth_layout)
    max_links_layout = QHBoxLayout()
    max_links_label = QLabel("Максимальна кількість лінків з однієї сторінки:")
    MAX_LINKS = QLineEdit()
    MAX_LINKS.setPlaceholderText("наприклад, 10")
    max_links_layout.addWidget(max_links_label)
    max_links_layout.addWidget(MAX_LINKS)
    form_layout.addLayout(max_links_layout)
    main_layout.addLayout(form_layout)
    START_BUT = QPushButton("Запустити пошук та PageRank")
    START_BUT.clicked.connect(start_crawling)
    main_layout.addWidget(START_BUT)
    log_label = QLabel("Процес обходу сторінок:")
    main_layout.addWidget(log_label)
    LOG_TXT = QTextEdit()
    LOG_TXT.setReadOnly(True)
    main_layout.addWidget(LOG_TXT, stretch=2)
    return WINDOW


def main():
    global APP
    APP = QApplication(sys.argv)
    win = build_gui()
    win.show()
    sys.exit(APP.exec_())


if __name__ == "__main__":
    main()
