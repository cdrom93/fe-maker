"""Stand-in for the decomp's tools/jsonproc (pokeemerald's, no license): JSON data through an Inja template.

Only the part of Inja the decomp's templates use (src/data/chapter_settings.json.txt and the three map
templates): `## for x in list` / `## endfor` line statements, `{{ a.b.c }}`, `upper(...)`,
`{% if ... %}{% else %}{% endif %}` with `existsIn(obj, "key")` or a value, and `doNotModifyHeader`.
The output is the same text, so the ROM stays byte for byte the same.
Usage: jsonproc.py DATA.json TEMPLATE.txt OUTPUT
"""

import json
import re
import sys

TOKEN = re.compile(r"\{\{(.*?)\}\}|\{%(.*?)%\}", re.S)
LINE_STATEMENT = re.compile(r"^[ \t]*## (.*)$")
CALL = re.compile(r"^(\w+)\((.*)\)$", re.S)
MISSING = object()


def tokenize(template):
    """Text, ("expr", source) and ("stmt", source) tokens; a `## ...` line is a statement without its line."""
    tokens = []
    text = []
    for line in template.splitlines(keepends=True):
        match = LINE_STATEMENT.match(line.rstrip("\r\n"))
        if match:
            tokens.extend(_inline("".join(text)))
            text = []
            tokens.append(("stmt", match.group(1).strip()))
        else:
            text.append(line)
    tokens.extend(_inline("".join(text)))
    return tokens


def _inline(text):
    tokens = []
    pos = 0
    for match in TOKEN.finditer(text):
        tokens.append(("text", text[pos:match.start()]))
        if match.group(1) is not None:
            tokens.append(("expr", match.group(1).strip()))
        else:
            tokens.append(("stmt", match.group(2).strip()))
        pos = match.end()
    tokens.append(("text", text[pos:]))
    return [token for token in tokens if token != ("text", "")]


def parse(tokens, pos=0, until=()):
    """A list of nodes up to one of the statements in `until`; returns (nodes, position, closing statement)."""
    nodes = []
    while pos < len(tokens):
        kind, value = tokens[pos]
        pos += 1
        if kind != "stmt":
            nodes.append((kind, value))
            continue
        word = value.split()[0]
        if word in until:
            return nodes, pos, word
        if word == "for":
            match = re.match(r"for\s+(\w+)\s+in\s+(.+)$", value)
            if not match:
                raise SyntaxError(value)
            body, pos, _ = parse(tokens, pos, ("endfor",))
            nodes.append(("for", match.group(1), match.group(2).strip(), body))
        elif word == "if":
            then, pos, end = parse(tokens, pos, ("else", "endif"))
            otherwise = []
            if end == "else":
                otherwise, pos, _ = parse(tokens, pos, ("endif",))
            nodes.append(("if", value[2:].strip(), then, otherwise))
        else:
            raise SyntaxError(f"unsupported statement: {value}")
    if until:
        raise SyntaxError(f"missing {until[-1]}")
    return nodes, pos, None


def split_args(source):
    args, depth, current, quoted = [], 0, "", False
    for char in source:
        if char == '"':
            quoted = not quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth -= 1
        elif not quoted and depth == 0 and char == ",":
            args.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        args.append(current.strip())
    return args


class Renderer:
    def __init__(self, data, json_path, template_path):
        self.data = data
        self.header = (f"//\n// DO NOT MODIFY THIS FILE! It is auto-generated from {json_path} "
                       f"and Inja template {template_path}\n//\n")

    def value(self, source, scope):
        source = source.strip()
        if source.startswith('"') and source.endswith('"'):
            return source[1:-1]
        if source == "doNotModifyHeader":
            return self.header
        call = CALL.match(source)
        if call:
            name, args = call.group(1), split_args(call.group(2))
            if name == "existsIn":
                obj = self.value(args[0], scope)
                return isinstance(obj, dict) and self.value(args[1], scope) in obj
            if name == "upper":
                return str(self.value(args[0], scope)).upper()
            if name == "doNotModifyHeader":
                return self.header
            raise SyntaxError(f"unsupported function: {name}")
        current = scope
        for part in source.split("."):
            if not isinstance(current, dict) or part not in current:
                return MISSING
            current = current[part]
        return current

    def text(self, value, source):
        if value is MISSING:
            raise KeyError(f"variable '{source}' not found")
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return value
        return json.dumps(value)

    def render(self, nodes, scope):
        out = []
        for node in nodes:
            kind = node[0]
            if kind == "text":
                out.append(node[1])
            elif kind == "expr":
                out.append(self.text(self.value(node[1], scope), node[1]))
            elif kind == "for":
                _, name, source, body = node
                items = self.value(source, scope)
                if items is MISSING:
                    raise KeyError(f"variable '{source}' not found")
                for item in items:
                    out.append(self.render(body, {**scope, name: item}))
            elif kind == "if":
                _, condition, then, otherwise = node
                value = self.value(condition, scope)
                out.append(self.render(then if value not in (MISSING, None, False, 0, "") else otherwise, scope))
        return "".join(out)


def main(argv):
    json_path, template_path, output_path = argv
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(template_path, encoding="utf-8") as f:
        nodes, _, _ = parse(tokenize(f.read()))
    text = Renderer(data, json_path, template_path).render(nodes, data)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main(sys.argv[1:])
