import json
from bs4 import BeautifulSoup
from bs4.element import Script
import re
import os
from urllib.request import urlopen
from logzero import logger, logfile


class Node:
    def __init__(self, name, ruby, id):
        self.parent = None
        self.children = []
        self.name = name
        self.ruby = ruby
        self.id = id

    def __repr__(self):
        return (
            f"id{self.id}:{self.name}. "
            f"parent: {self.parent['name'] if self.parent else 'None'}, "
            f"child: [{', '.join([child.name for child in self.children])}]."
        )

    def __str__(self):
        return self.name + f"（{self.ruby}）"


class Tree:
    def __init__(self):
        self.root = Node("root", "root", 0)
        self.nodes_num = 1

    def add(self, name, ruby, parents_set, disambiguation=None):
        # 新規ノードの名前と, それが親世代として持つ名前のリストを受け取って新しいノードを追加する.
        new_node = Node(name, ruby, self.nodes_num)
        # 曖昧性回避用文字列が設定されているなら属性としてもたせる
        if disambiguation:
            new_node.disambiguation = disambiguation
        current_node = self.root  # 上から順番に見ていくために保持するnode
        if parents_set:
            # 親世代をすべてみつけるまでループ
            while parents_set:
                # 今見ているノードの子を集合としてとる
                current_children_set = set(
                    child.name for child in current_node.children
                )
                next_node_name = (parents_set & current_children_set).pop()
                parents_set.discard(next_node_name)
                if current_node.children:
                    current_node = [
                        child
                        for child in current_node.children
                        if child.name == next_node_name
                    ][0]
            new_node.parent = current_node
        else:
            new_node.parent = self.root
        current_node.children.append(new_node)
        self.nodes_num += 1

    def print_childtree(self, node, recr=True, acc=""):
        if recr:
            if not node.children:
                print(acc + node.name)
                return
            else:
                for next_node in node.children:
                    self.print_childtree(next_node, True, acc + node.name + "--")
        else:
            for next_node in node.children:
                self.print_childtree(next_node, False)

    def leaf_generator(self, node):
        # node以下の葉ノードのgeneratorを返す. self.rootを指定すれば全ての葉のイテレータになる.
        if node.children:
            for child in node.children:
                yield from self.leaf_generator(child)
        else:
            yield node


def get_source():
    FILE_PATH = "./wiki_page.html"
    URL = (
        "https://ja.wikipedia.org/wiki/"
        "%E6%97%A5%E6%9C%AC%E3%81%AE%E5%9C%B0"
        "%E6%96%B9%E5%85%AC%E5%85%B1%E5%9B%A3%E4%BD%93%E4%B8%80%E8%A6%A7"
    )
    # ソースのhtmlが存在しなければ取ってきて保存し, あるならそれを使う.
    if not os.path.exists(FILE_PATH):
        print("source not exists. fetching...")
        with urlopen(URL) as response:
            html = response.read()
            with open(FILE_PATH, mode="wb") as f:
                f.write(html)
        print("done.")
    with open(FILE_PATH) as f:
        html = f.read()
    return html


def get_data_obj():
    logfile("./parse_log.log")

    html = get_source()
    bs = BeautifulSoup(html, "html.parser")
    scr_contents = "".join(
        bs.select("script")[0].get_text(types=(Script,)).splitlines()
    )
    # !1などがデータに含まれており正常に読めないので置換
    scr_contents = scr_contents.replace("!", "-")
    json_str_match = re.search(r"RLCONF=(.*?);", scr_contents)
    if json_str_match:
        json_str = json_str_match.groups()[0]
        try:
            obj = json.loads(json_str)
        except json.decoder.JSONDecodeError as e:
            print(e)
            print(json_str[0:30])
            print(json_str[-30:])
    else:
        logger.error("(json str) match object is empty.")

    subobj = obj["wgGraphSpecs"]["443a4f936911bcdc9c09725722ce4df318bcbdef"]["data"][1][
        "values"
    ]
    subobj = [
        {k: data[k] for k in data if k != "so" and k != "code"} for data in subobj
    ]
    # subobjはリストに書かれるデータの配列になっている.
    # これから木構造を作成して, その後目的のデータ構造にパースする.
    return subobj


def making_tree(obj):
    tree = Tree()
    for data in obj:
        name = data["name"]
        ruby = data["kana"]

        parents_set = set(data["parent"].split())  # スペース区切りなのでsplitしてリストにし, setに直す
        # 最後が区で終わっていて東京都を親に持たないなら木に含めない
        if name[-1] == "区" and "東京都" not in parents_set:
            continue
        if "disambiguation" in data:
            tree.add(name, ruby, parents_set, "（" + data["disambiguation"] + "）")
        else:
            tree.add(name, ruby, parents_set)
    return tree


def make_json_data(tree):
    result = []
    for node in tree.leaf_generator(tree.root):
        manicipality = {}
        current_node = node
        fullname = ""
        name = node.name
        has_county = bool(node.name[-1] in ["町", "村"])
        while current_node.name != "root":
            fullname = current_node.name + fullname
            # 町か村で終わっているなら郡を探してそれもくっつける.
            # 東京都島嶼部は上をたどっても郡はないので無視できる.
            if has_county and current_node.name[-1] == "郡":
                name = current_node.name + name
            current_node = current_node.parent

        manicipality["fullname"] = fullname
        # manicipality["name"] = getattr(node, "disambiguation", "") + node.name
        manicipality["name"] = name
        manicipality["smallText"] = node.ruby
        result.append(manicipality)

    return json.dumps(result, indent=2, ensure_ascii=False)


def main():
    obj = get_data_obj()
    tree = making_tree(obj)
    # tree.print_childtree(tree.root)
    result = make_json_data(tree)
    with open("./manicipalities.json", mode="w") as f:
        f.write(result)


if __name__ == "__main__":
    main()
