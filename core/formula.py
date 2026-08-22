# -*- coding: utf-8 -*-
"""FormulaRule:反应扩散公式表达式解析 → numpy 闭包。净室实现。

语法(自设计,语义对齐公开反应扩散文献惯例):
  delta_<chem> = <expr>;
  变量:化学名(a,b,...)/ laplacian_<chem> / 参数名 / 数值常量
  运算符:+ - * / ^ 一元负号 括号
  <expr> 逐项求值,delta 为增量(Euler:chem += delta*dt)

示例(公开论文公式):
  delta_a = D_a * laplacian_a - a*b*b + F*(1.0-a);
  delta_b = D_b * laplacian_b + a*b*b - (F+k)*b;
"""
from __future__ import annotations
import re
import numpy as np

TOKEN_RE = re.compile(r"""
    \s*(?:
        (?P<num>\d+\.\d*|\.\d+|\d+)
      | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<op>[+\-*/^()])
      | (?P<sep>;|=)
    )""", re.VERBOSE)


class FormulaError(ValueError):
    pass


def tokenize(src: str):
    pos = 0
    toks = []
    while pos < len(src):
        c = src[pos]
        if c in " \t\n\r":
            pos += 1
            continue
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise FormulaError(f"无法识别的字符: {src[pos:pos+10]!r} @{pos}")
        pos = m.end()
        kind = m.lastgroup
        val = m.group()
        if kind == "num":
            toks.append(("num", float(val)))
        elif kind == "ident":
            toks.append(("ident", val))
        elif kind == "op":
            toks.append(("op", val))
        elif kind == "sep":
            toks.append(("sep", val))
    toks.append(("eof", None))
    return toks


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind, val=None):
        t = self.next()
        if t[0] != kind or (val is not None and t[1] != val):
            raise FormulaError(f"期望 {val or kind},得到 {t}")
        return t

    def parse_statements(self):
        stmts = []
        while self.peek()[0] != "eof":
            if self.peek()[0] == "sep" and self.peek()[1] == ";":
                self.next()
                continue
            stmts.append(self.parse_statement())
            if self.peek()[0] == "sep" and self.peek()[1] == ";":
                self.next()
        return stmts

    def parse_statement(self):
        lhs = self.expect("ident")[1]
        self.expect("sep", "=")
        rhs = self.parse_expr()
        return (lhs, rhs)

    def parse_expr(self):
        return self.parse_add()

    def parse_add(self):
        node = self.parse_mul()
        while self.peek()[0] == "op" and self.peek()[1] in ("+", "-"):
            op = self.next()[1]
            right = self.parse_mul()
            node = (op, node, right)
        return node

    def parse_mul(self):
        node = self.parse_pow()
        while self.peek()[0] == "op" and self.peek()[1] in ("*", "/"):
            op = self.next()[1]
            right = self.parse_pow()
            node = (op, node, right)
        return node

    def parse_pow(self):
        node = self.parse_unary()
        if self.peek()[0] == "op" and self.peek()[1] == "^":
            self.next()
            right = self.parse_pow()
            node = ("pow", node, right)
        return node

    def parse_unary(self):
        if self.peek()[0] == "op" and self.peek()[1] == "-":
            self.next()
            return ("neg", self.parse_unary())
        if self.peek()[0] == "op" and self.peek()[1] == "+":
            self.next()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        t = self.peek()
        if t[0] == "num":
            self.next()
            return ("num", t[1])
        if t[0] == "ident":
            self.next()
            return ("var", t[1])
        if t[0] == "op" and t[1] == "(":
            self.next()
            node = self.parse_expr()
            self.expect("op", ")")
            return node
        raise FormulaError(f"意外 token: {t}")


def _eval(node, env):
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "var":
        name = node[1]
        if name not in env:
            raise FormulaError(f"未定义变量: {name}")
        return env[name]
    if kind == "neg":
        return -_eval(node[1], env)
    if kind == "pow":
        return _eval(node[1], env) ** _eval(node[2], env)
    if kind in ("+", "-", "*", "/"):
        a, b = _eval(node[1], env), _eval(node[2], env)
        return {"+": lambda: a + b, "-": lambda: a - b,
                "*": lambda: a * b, "/": lambda: a / b}[kind]()
    raise FormulaError(f"未知节点: {kind}")


class FormulaRule:
    """解析一组 delta 语句,生成可复用的 numpy 更新闭包。

    用法示例(见 tests/test_formula.py)。"""

    def __init__(self, src, chemical_names=None):
        self.src = src
        self.statements = Parser(tokenize(src)).parse_statements()
        # 收集变量名
        vars_used = set()
        for lhs, rhs in self.statements:
            self._collect(rhs, vars_used)
        lhs_names = [s[0] for s in self.statements]
        self.chem_names = [n for n in lhs_names if n.startswith("delta_")]
        if not self.chem_names:
            raise FormulaError("未找到 delta_<chem> 语句")
        # 审查修复:非 delta_ 左值在解析期明确拒绝,避免运行期误导报错
        for lhs in lhs_names:
            if not lhs.startswith("delta_"):
                raise FormulaError(
                    f"不支持的非 delta_ 左值: {lhs!r}(只支持 delta_<chem> = <expr>; 语句)")
        if chemical_names is None:
            # 按 delta 语句顺序推断化学名
            chemical_names = [n.split("_", 1)[1] for n in self.chem_names]
        self.chemical_names = chemical_names
        self.param_names = sorted(
            v for v in vars_used
            if not (v.startswith("laplacian_") or v in chemical_names
                    or v.startswith("delta_") or v == "dt"))

    def _collect(self, node, acc):
        kind = node[0]
        if kind == "var":
            acc.add(node[1])
        elif kind == "num":
            pass
        elif kind == "neg":
            self._collect(node[1], acc)
        elif kind in ("+", "-", "*", "/", "pow"):
            self._collect(node[1], acc)
            self._collect(node[2], acc)

    def describe_parameters(self):
        """参数清单(默认值留空,由调用方指定)。"""
        return [(p, None) for p in self.param_names]

    def update(self, fields, params, dt=1.0, field_kind="grid", nbr=None, wrap=False):
        """fields: dict 或 list。推荐 dict {chem_name: ndarray}。

        注意(审查修复):wrap 优先从 params 读取(与 NumpyBackend 传参方式一致),
        否则取关键字默认。
        """
        wrap = params.get("wrap", wrap) if isinstance(params, dict) else wrap
        if isinstance(fields, dict):
            env = dict(fields)
        else:
            env = {n: f for n, f in zip(self.chemical_names, fields)}
        env.update(params)
        # 计算 laplacian
        try:
            from .ops import laplacian_5, graph_laplacian
        except ImportError:
            from core.ops import laplacian_5, graph_laplacian
        # 先收集需要 laplacian 的化学名(避免迭代时修改 dict)
        lap_names = {}
        for name, f in list(env.items()):
            if isinstance(f, np.ndarray):
                lap_name = f"laplacian_{name}"
                if field_kind == "grid":
                    lap_names[lap_name] = laplacian_5(f, wrap)
                else:
                    lap_names[lap_name] = graph_laplacian(f, nbr[0], nbr[1])
        env.update(lap_names)
        # 逐语句求 delta
        deltas = {}
        for lhs, rhs in self.statements:
            deltas[lhs] = _eval(rhs, env)
        # 应用 Euler 步进(就地修改,保持对调用方数组的引用)
        for lhs, d in deltas.items():
            chem = lhs.split("_", 1)[1]
            env[chem] += d * dt
        return [env[n] for n in self.chemical_names]
