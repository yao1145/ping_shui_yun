# -*- coding: utf-8 -*-
"""平水韵查询工具：输入字查韵部，输入韵部查字。

依赖同目录下的两个数据文件：
  baseCharDict.json  按字查询（键为汉字，值为读音列表）
  oriYunDict.json    按韵部查询（键为“韵部名+声调”，值为韵字串）
"""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAR_DICT = os.path.join(BASE_DIR, 'baseCharDict.json')
YUN_DICT = os.path.join(BASE_DIR, 'oriYunDict.json')

CN_NUM = '零一二三四五六七八九'

# 数据中个别韵名 OCR 讹误，加载与查询时统一修正
YUN_ALIAS = {'二十一个': '二十一箇'}


def num_to_cn(n):
    """阿拉伯数字转中文数字（1~30）。"""
    if n < 10:
        return CN_NUM[n]
    if n == 10:
        return '十'
    if n < 20:
        return '十' + CN_NUM[n % 10]
    tens, ones = divmod(n, 10)
    return CN_NUM[tens] + '十' + (CN_NUM[ones] if ones else '')


def cn_to_num(s):
    """中文数字转阿拉伯数字（零/一~三十）。"""
    if not s:
        return None
    if s in CN_NUM:
        return CN_NUM.index(s)
    if '十' in s:
        tens, _, ones = s.partition('十')
        t = CN_NUM.index(tens) if tens else 1
        o = CN_NUM.index(ones) if ones else 0
        return t * 10 + o
    return None


def norm_yun_name(name):
    """韵部名归一化：去掉 BOM/空白，阿拉伯数字转中文数字。"""
    name = name.replace('\ufeff', '').strip()
    m = re.match(r'^(\d+)', name)
    if m:
        return num_to_cn(int(m.group(1))) + name[len(m.group(1)):]
    return name


def load_data():
    """加载两个 JSON，容错解码并归一化。"""
    char_raw = open(CHAR_DICT, 'rb').read().decode('utf-8', errors='replace')
    yun_raw = open(YUN_DICT, 'rb').read().decode('utf-8', errors='replace')
    char_dict = json.loads(char_raw)
    yun_dict = json.loads(yun_raw)

    # 归一化 baseCharDict 中的韵部字段
    for ch, entries in char_dict.items():
        for entry in entries:
            if len(entry) >= 2:
                entry[1] = norm_yun_name(entry[1])

    # 解析 oriYunDict 的 key：如 “一东平”“十五合入” → (韵部名, 声调)
    yun_index = {}          # {(韵部名, 声调): 韵字串}
    yun_names = set()       # 所有韵部名
    for key, value in yun_dict.items():
        key = key.replace('\ufeff', '').strip()
        m = re.match(r'^([一二三四五六七八九十]+)(.+?)([平上去入])$', key)
        if m:
            num, name, tone = m.groups()
            name = num_to_cn(cn_to_num(num)) + name
            name = YUN_ALIAS.get(name, name)
            yun_index[(name, tone)] = value
            yun_names.add(name)
    return char_dict, yun_index, yun_names


def query_char(char_dict, ch):
    """查单字，返回 [(声调, 韵部, 备注), ...] 或 None。"""
    return char_dict.get(ch)


def query_yun(yun_index, q):
    """查韵部。返回 (韵部名, 声调, 韵字串) 列表，无命中返回空列表。"""
    q = q.replace('\ufeff', '').strip()
    if not q:
        return []
    q = YUN_ALIAS.get(q, q)

    # 去掉 “上平/下平” 前缀
    for pre in ('上平', '下平'):
        if q.startswith(pre):
            q = q[len(pre):]
            break

    # 阿拉伯数字开头 → 转中文数字
    m = re.match(r'^(\d+)', q)
    if m:
        q = num_to_cn(int(m.group(1))) + q[len(m.group(1)):]

    results = []

    # 1) 数字 + 韵名 + 声调（如 “一东平”）
    m = re.match(r'^([一二三四五六七八九十]+)(.+?)([平上去入])$', q)
    if m:
        n = cn_to_num(m.group(1))
        if n is not None:
            name = num_to_cn(n) + m.group(2)
            key = (name, m.group(3))
            if key in yun_index:
                results.append(key + (yun_index[key],))
                return results

    # 2) 纯数字（如 “一”“十五”）：列出该数字下全部韵部
    m = re.match(r'^([一二三四五六七八九十]+)$', q)
    if m:
        n = cn_to_num(m.group(1))
        if n is not None:
            matches = []
            for (name, tone), v in yun_index.items():
                m2 = re.match(r'^([一二三四五六七八九十]+)', name)
                if m2 and cn_to_num(m2.group(1)) == n:
                    matches.append((name, tone, v))
            return matches

    # 3) 数字 + 韵名（如 “一东”“十五合”）

    m = re.match(r'^([一二三四五六七八九十]+)(.+)$', q)
    if m:
        n = cn_to_num(m.group(1))
        if n is not None:
            name = num_to_cn(n) + m.group(2)
            matches = [k + (v,) for k, v in yun_index.items() if k[0] == name]
            if matches:
                return matches

    # 3) 韵名模糊匹配（如 “东” → 一东；“合” → 十五合）
    return [k + (v,) for k, v in yun_index.items() if q in k[0]]


def wrap(text, width):
    """按显示宽度折行，返回多行字符串。"""
    return '\n'.join(text[i:i + width] for i in range(0, len(text), width))


def show_char(char_dict, ch):
    entries = query_char(char_dict, ch)
    if not entries:
        return False
    print(f'「{ch}」共 {len(entries)} 个读音：')
    for tone, yun, note in entries:
        suffix = f'（{note}）' if note else ''
        print(f'  {tone}声 {yun}{suffix}')
    return True


def show_yun(yun_index, matches, q):
    if not matches:
        return False
    if len(matches) > 1:
        print(f'“{q}”匹配到 {len(matches)} 个韵部：')
        for name, tone, _ in matches:
            print(f'  {name}（{tone}声）')
        print('输入“韵 <韵部名>”可查看某部内容。')
    else:
        (name, tone, text), = matches
        text = text.replace('\ufeff', '')
        print(f'韵部「{name}」（{tone}声）共 {len(text)} 字：')
        print(wrap(text, 40))
    return True


def show_help():
    print(__doc__)
    print('使用说明：')
    print('  输入汉字      -> 查该字所属的所有韵部')
    print('  输入韵部      -> 查该韵部的所有字，如：一东 / 东 / 1 / 十五合')
    print('  韵部可带声调   -> 如：一东平、十五合入')
    print('  上平/下平前缀 -> 如：上平一东、下平十五')
    print('  强制前缀      -> 字 <汉字> 强制查字；韵 <韵部> 强制查韵部')
    print('  输入 q/exit   -> 退出')


def main():
    if not (os.path.exists(CHAR_DICT) and os.path.exists(YUN_DICT)):
        print('缺少数据文件 baseCharDict.json / oriYunDict.json，请与本程序放在同一目录。')
        return
    char_dict, yun_index, _ = load_data()
    print(f'数据加载完成：{len(char_dict)} 字，{len(yun_index)} 韵部。')
    print('输入“help”查看帮助，输入“q”退出。')

    while True:
        try:
            raw = input('\n> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        if raw.lower() in ('q', 'quit', 'exit'):
            break
        if raw.lower() in ('help', 'h', '?'):
            show_help()
            continue

        force_char = raw.startswith('字 ')
        force_yun = raw.startswith('韵 ') or raw.startswith('部 ')

        if force_char:
            ch = raw[2:].strip()
            if not show_char(char_dict, ch):
                print(f'未找到“{ch}”')
        elif force_yun:
            q = raw[2:].strip()
            if not show_yun(yun_index, query_yun(yun_index, q), q):
                print(f'未找到韵部“{q}”')
        elif len(raw) == 1 and re.match(r'[\u4e00-\u9fff]', raw):
            # 单汉字：先查字，若同是韵部名再附韵部
            show_char(char_dict, raw)
            matches = query_yun(yun_index, raw)
            if matches:
                print(f'（“{raw}”同时是韵部名：{", ".join(n + "·" + t for n, t, _ in matches)}）')
                for name, tone, text in matches:
                    print(f'  韵部「{name}」（{tone}声）{len(text)} 字：')
                    print('    ' + wrap(text.replace("\ufeff", ""), 40).replace('\n', '\n    '))
        else:
            if not show_yun(yun_index, query_yun(yun_index, raw), raw):
                if len(raw) == 1:
                    if not show_char(char_dict, raw):
                        print(f'未找到“{raw}”')
                else:
                    print(f'未找到与“{raw}”匹配的内容')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    main()
