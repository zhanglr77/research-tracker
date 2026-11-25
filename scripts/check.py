#!/usr/bin/env python3
"""只校验，不生成看板。用法：python3 check.py <根目录>

退出码：0 = 没有必须修的错误（可能有纪律警告）；1 = 有必须修的错误；2 = 用法不对。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracker as T
import lockfile as L


def main(argv):
    if len(argv) != 2:
        print('用法：python3 check.py <根目录>')
        return 2
    try:
        data = T.load_all(argv[1], lock=L.read(argv[1]))
    except T.TrackerError as e:
        print('有 %d 处必须修的错误：' % len(e.errors))
        for x in e.errors:
            print('  ✗ ' + x)
        return 1
    print(L.summary(data))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
