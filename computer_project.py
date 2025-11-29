def read_file(file_name: str) -> list[str]:
    with open(file_name, 'r', encoding='utf-8') as file:
        file_con = file.readlines()
    return file_con

def create_dictionaries(file_content: list[str]) -> tuple:
    vertical_out = {}
    vertical_in = {}
    page_rank = {}
    vertexes = set()
    not_used_vertexes = set()
    end_point = ''
    for elem in file_content[1:-1]:
        elem = elem.replace('\n', '').replace(' ', '')
        if '->' in elem:
            start_point, end_point = elem.split('->')
        else:
            start_point = elem.strip()
        if not start_point:
            continue
        if end_point and start_point:
            vertical_out.setdefault(start_point, set()).add(end_point)
            vertical_in.setdefault(end_point, set()).add(start_point)
        if start_point:
            vertexes.add(start_point)
        if end_point:
            vertexes.add(end_point)
        start_point, end_point = '', ''
    for point in vertexes:
        if point not in vertical_out and point not in vertical_in:
            not_used_vertexes.add(point)
    if start_point:
        vertexes.add(start_point)
    if end_point:
        vertexes.add(end_point)
    page_rank = page_rank.fromkeys(vertexes, 1/len(vertexes))
    page_rank = dict(sorted(page_rank.items(), key=lambda x: x[0]))
    return vertical_in, vertical_out, page_rank, vertexes, not_used_vertexes

def get_page_rank(page_rank, out_in_ribs, in_out_ribs, peaks, useless_peaks):
    all_vertexes_counter = len(peaks)
    previous_pr = page_rank.copy()
    all_peaks = peaks | useless_peaks
    start = True
    no_exit_vert = [vert for vert in peaks if vert not in out_in_ribs]
    while start or any(abs(previous_pr[value] - page_rank[value]) > 1e-6 for value in page_rank):
        start = False
        previous_pr = page_rank.copy()
        dangling_sum = sum(previous_pr[v] for v in no_exit_vert) ## cont S = sum(prev[v] for v in dangling)
        for peak in all_peaks:
            coefficients_sum = 0
            if peak in in_out_ribs: #Якщо вершина має вхід
                for point in in_out_ribs[peak]:
                    point_rank = previous_pr[point]
                    point_outs = len(out_in_ribs[point])
                    coefficients_sum += point_rank/point_outs
            
            page_rank[peak] = (1 - 0.85)/all_vertexes_counter + 0.85*(coefficients_sum + dangling_sum/all_vertexes_counter)
    return page_rank


if __name__ == '__main__':
    file_c = read_file('graph_in.dot')
    vertical_in_1, vertical_out_1, pagerank, vertex, not_used_vertex = create_dictionaries(file_c)
    print(get_page_rank(pagerank, vertical_out_1, vertical_in_1, vertex, not_used_vertex))
