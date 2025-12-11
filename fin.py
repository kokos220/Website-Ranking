"""PageRank crawler with PyQt5"""

import sys
import re
from urllib.parse import urljoin, urldefrag
from urllib.request import urlopen, Request

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QTextEdit
from PyQt5.QtWidgets import QMessageBox

APP = None
WINDOW = None
URL_EDIT = None
DEPTH_EDIT = None
MAX_LINKS = None
START_BUT = None
LOG_TXT = None

def read_file(file_name: str) -> list[str]:
    """
    Зчитує текстовий файл з описом графа посилань.

    Кожен рядок файлу має формат:
        url -> url

    :param file_name: str, шлях до файлу (наприклад, "menu.dot").
    :return: list[str], список рядків файлу без додаткової обробки.
    """
    with open(file_name, 'r', encoding='utf-8') as file:
        file_con = file.readlines()
    return file_con

def create_dictionaries(file_content: list[str]) -> tuple:
    """
    Створює словники структури графа за вмістом файлу.

    Зі списку рядків формату "src -> dst" будує:
      vertical_in – словник {вершина: множина вхідних сусідів};
      vertical_out – словник {вершина: множина вихідних сусідів};
      page_rank – словник початкових значень PageRank;
      vertexes – множина всіх вершин, які зустрілися в ребрах;
      not_used_vertexes – множина вершин без ребер.

    :param file_content: list[str], список рядків файлу з ребрами графа.
    :return: tuple[dict, dict, dict, set, set], кортеж 
    (vertical_in, vertical_out, page_rank, vertexes, not_used_vertexes).
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
    Обчислює значення PageRank для заданого орієнтованого графа.

    Використовується класична ітеративна формула PageRank:
        PR(v) = (1 - d) / N + d * (сума по всіх u, які ведуть у v) +
        внесок "висячих" вершин.

    Ітерації тривають, доки зміни PR для всіх вершин не стануть
    меншими за 1e-6.

    :param page_rank: dict[str, float], початковий словник PageRank.
    :param out_in_ribs: dict[str, set[str]], словник вихідних ребер
        {вершина: множина сусідів, куди є ребро}.
    :param in_out_ribs: dict[str, set[str]], словник вхідних ребер
        {вершина: множина вершин, звідки є ребро}.
    :param peaks: set[str], множина вершин графа.
    :param useless_peaks: set[str], множина не потрібних вершин.
    :return: dict[str, float], словник PageRank-значень, відсортований
        за спаданням значення.
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
    """
    Виводить повідомлення у QTextEdit та оновлює інтерфейс.

    Якщо глобальна змінна LOG_TXT не None, то додається рядок
    до текстового поля логів, курсор переноситься в кінець,
    а події Qt обробляються для оновлення GUI.

    :param msg: str, текст повідомлення для виводу.
    """
    global LOG_TXT
    if LOG_TXT is not None:
        LOG_TXT.append(msg)
        LOG_TXT.moveCursor(LOG_TXT.textCursor().End)
        QApplication.processEvents()

def search_links(start_url: str, max_depth: int, output_path: str, max_links_per_page: int):
    """
    Рекурсивно обходить веб-сторінки, починаючи з початкової URL-адреси,
    та записує знайдені посилання у файл.

    Кожен знайдений перехід записується у файл у форматі:
        source_url -> destination_url

    Обмеження:
      максимальна глибина обходу (max_depth);
      максимальна кількість посилань, взятих з однієї сторінки
      (max_links_per_page);
      пропускаються технічні/непотрібні посилання.

    :param start_url: str, URL, з якої починається обхід.
    :param max_depth: int, максимальна глибина рекурсії.
    :param output_path: str, шлях до файлу, куди будуть записані ребра графа.
    :param max_links_per_page: int, максимальна кількість посилань,
        які беруться з однієї сторінки.
    """
    visited = set()
    href_pattern = r'href\s*=\s*["\']([^"\']+)["\']'
    def is_url(url: str) -> bool:
        """
        Перевіряє, чи є рядок повноцінною HTTP(S)-URL-адресою.

        :param url: str, рядок для перевірки.
        :return: bool, True, якщо починається з "http://" або "https://",
                 інакше False.
        """
        return url.startswith("http://") or url.startswith("https://")
    def get_html(url: str) -> str | None:
        """
        Завантажує HTML-вміст сторінки за вказаною URL-адресою.

        Використовує простий HTTP-запит з User-Agent, декодує
        відповідь як UTF-8 з ігноруванням помилок.

        :param url: str, URL сторінки, яку потрібно завантажити.
        :return: str | None, текст HTML або None, якщо сталася помилка
            (таймаут, помилка мережі тощо).
        """
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=5) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return None
    with open(output_path, "w", encoding="utf-8") as f_out:
        def write_line(src: str, dst: str):
            """
            Записує ребро графа у файл.

            Формат рядка:
                src -> dst

            :param src: str, вихідна сторінка.
            :param dst: str, цільова сторінка.
            """
            f_out.write(f"{src} -> {dst}\n")
        def search(url: str, depth: int):
            """
            Рекурсивна функція обходу посилань з однієї сторінки.

            Для кожної сторінки:
              завантажує HTML;
              знаходить усі href-посилання;
              фільтрує зайві/непотрібні;
              нормалізує URL (urljoin + urldefrag);
              записує перехід у файл;
              рекурсивно продовжує обхід до заданої глибини.

            :param url: str, поточна сторінка для обходу.
            :param depth: int, поточна глибина рекурсії.
            """
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
    Запускає crawler, будує файл графа, рахує PageRank і виводить топ-10.

    Кроки:
      Викликає search_links для побудови файлу з ребрами ("menu.dot").
      Зчитує файл і створює словники графа (create_dictionaries).
      Обчислює PageRank для всіх вершин (get_page_rank).
      Виводить у LOG_TXT топ-10 сторінок за рейтингом.

    У разі помилки показує діалогове вікно з повідомленням.

    :param url: str, початкова URL для обходу.
    :param depth: int, максимальна глибина пошуку (для crawler).
    :param max_links: int, максимальна кількість посилань з однієї сторінки.
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
    """
    Обробляє натискання кнопки старту, зчитує дані з полів і запускає обхід.

    Кроки:
      Зчитує URL, глибину та max_links з полів вводу.
      Перевіряє, що URL непорожній.
      Перетворює глибину та кількість лінків на int та перевіряє,
      що вони додатні.
      Очищує лог, блокує кнопку старту.
      Викликає run_crawler_and_pagerank зі зчитаними параметрами.

    У разі некоректного вводу показує попередження через QMessageBox.
    """
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
    Створює та налаштовує головне вікно графічного інтерфейсу.

    Вікно містить:
      поле для вводу початкового URL;
      поле для вводу максимальної глибини пошуку;
      поле для вводу максимальної кількості лінків з однієї сторінки;
      кнопку запуску обходу та обчислення PageRank;
      QTextEdit для відображення логів виконання.

    Глобальні змінні WINDOW, URL_EDIT, DEPTH_EDIT, MAX_LINKS,
    START_BUT, LOG_TXT заповнюються посиланнями на відповідні віджети.

    :return: QWidget, створене головне вікно QWidget.
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
    """
    Точка входу в програму.

    Створює QApplication, будує GUI за допомогою build_gui(),
    показує головне вікно та запускає головний цикл подій Qt.
    """
    global APP
    APP = QApplication(sys.argv)
    win = build_gui()
    win.show()
    sys.exit(APP.exec_())


if __name__ == "__main__":
    main()
