from __future__ import annotations

import fnmatch
import os
import posixpath
import re
import sys
from dataclasses import dataclass, field
from types import MappingProxyType, GenericAlias
from typing import Literal
from collections.abc import Sequence

_MAPPING = {"-": 0, "a": 1, "m": 2, "v": 4}


class NodeState:
    AVAILABLE = 1
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者默认情况下对该节点的子节点拥有使用权限
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者对该节点拥有使用权限，表示对节点对应的实际内容可用
    """

    MODIFY = 2
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者可以增加、删除、修改该节点的子节点（无论子节点的权限是怎样的）
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者可以修改该节点的内容
    """

    VISIT = 4
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者可以访问该节点的子节点
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者可以查看节点的状态和内容
    """

    def __init__(self, state: int | str):
        if isinstance(state, str):
            state = sum(_MAPPING[i] for i in state.lower() if i in _MAPPING)
        if state < 0 or state > 7:
            raise ValueError("state must be in range [0, 7]")
        self.state = state

    @property
    def available(self):
        return self.state & NodeState.AVAILABLE == NodeState.AVAILABLE

    @property
    def modify(self):
        return self.state & NodeState.MODIFY == NodeState.MODIFY

    @property
    def visit(self):
        return self.state & NodeState.VISIT == NodeState.VISIT

    def __repr__(self):
        state = ["-", "-", "-"]
        if self.available:
            state[2] = "a"
        if self.modify:
            state[1] = "m"
        if self.visit:
            state[0] = "v"
        return "".join(state)


CHILD_MAP: dict[str, set[str]] = {"/": set()}


@dataclass(repr=False, eq=True, unsafe_hash=True)
class File:
    type: Literal["file", "dir"]
    path: str
    content: dict[str, str] = field(compare=False, hash=False)

    def __post_init__(self):
        if self.type == "dir":
            CHILD_MAP[self.path] = set()

    @property
    def isdir(self):
        return self.type == "dir"

    @property
    def isfile(self):
        return self.type == "file"

    def __repr__(self):
        return f"{'DIR' if self.isdir else 'FILE'}({self.path!r})"


INDEX_MAP: dict[str, File] = {"/": File("dir", "/", {})}


class _Flavour(object):
    """A flavour implements a particular (platform-specific) set of node
    semantics."""

    def __init__(self):
        self.sep = "/"
        self.altsep = ""
        self.join = self.sep.join

    def parse_parts(self, parts):
        parsed = []
        sep = self.sep
        altsep = self.altsep
        root = ""
        it = reversed(parts)
        for part in it:
            if not part:
                continue
            if altsep:
                part = part.replace(altsep, sep)
            root, rel = self.splitroot(part)
            if sep in rel:
                for x in reversed(rel.split(sep)):
                    if x and x != ".":
                        parsed.append(sys.intern(x))
            else:
                if rel and rel != ".":
                    parsed.append(sys.intern(rel))
        if root:
            parsed.append(root)
        parsed.reverse()
        return root, parsed

    def join_parsed_parts(self, root, parts, root2, parts2):
        """
        Join the two nodes represented by the respective
        (root, parts) tuples.  Return a new (root, parts) tuple.
        """
        if not root2:
            # Second node is non-anchored (common case)
            return root, parts + parts2
        return root2, parts2

    def splitroot(self, part, sep="/"):
        if part and part[0] == sep:
            stripped_part = part.lstrip(sep)
            if len(part) - len(stripped_part) == 2:
                return sep * 2, stripped_part
            else:
                return sep, stripped_part
        else:
            return "", part

    def casefold(self, s):
        return s

    def casefold_parts(self, parts):
        return parts

    def compile_pattern(self, pattern):
        return re.compile(fnmatch.translate(pattern)).fullmatch

    def resolve(self, node):
        sep = self.sep

        def _resolve(node, rest):
            if rest.startswith(sep):
                node = ""

            for name in rest.split(sep):
                if not name or name == ".":
                    # current dir
                    continue
                if name == "..":
                    # parent dir
                    node, _, _ = node.rpartition(sep)
                    continue
                if node.endswith(sep):
                    newnode = node + name
                else:
                    newnode = node + sep + name
                node = newnode

            return node

        base = "" if node.is_absolute() else _get_current()
        return _resolve(base, str(node)) or sep

    def is_reserved(self, parts):
        return False


_flavour = _Flavour()


class _NodeParents(Sequence):
    """This object provides sequence-like access to the logical ancestors
    of a node.  Don't try to construct it yourself."""

    __slots__ = ("_nodecls", "_root", "_parts")

    def __init__(self, node: "Node"):
        # We don't store the instance to avoid reference cycles
        self._nodecls = type(node)
        self._root = node._root
        self._parts = node._parts

    def __len__(self):
        if self._root:
            return len(self._parts) - 1
        else:
            return len(self._parts)

    def __getitem__(self, idx):
        if idx < 0 or idx >= len(self):
            raise IndexError(idx)
        return self._nodecls._from_parsed_parts(self._root, self._parts[: -idx - 1])

    def __repr__(self):
        return "<Node.parents>"


class Node:
    __slots__ = (
        "_root",
        "_parts",
        "_str",
        "_hash",
        "_pparts",
        "_cached_cparts",
    )

    def __new__(cls, *args, **kwargs):
        self = cls._from_parts(args, init=False)
        self._init()
        return self

    def __reduce__(self):
        # Using the parts tuple helps share interned node parts
        # when pickling related nodes.
        return self.__class__, tuple(self._parts)

    @classmethod
    def _parse_args(cls, args):
        # This is useful when you don't want to create an instance, just
        # canonicalize some constructor arguments.
        parts = []
        for a in args:
            if isinstance(a, Node):
                parts += a._parts
            else:
                a = os.fspath(a)
                if isinstance(a, str):
                    # Force-cast str subclasses to str (issue #21127)
                    parts.append(str(a))
                else:
                    raise TypeError(
                        "argument should be a str object or an os.PathLike " "object returning str, not %r" % type(a)
                    )
        return _flavour.parse_parts(parts)

    @classmethod
    def _from_parts(cls, args, init=True):
        self = object.__new__(cls)
        root, parts = self._parse_args(args)
        self._root = root
        self._parts = parts
        if init:
            self._init()
        return self

    @classmethod
    def _from_parsed_parts(cls, root, parts, init=True):
        self = object.__new__(cls)
        self._root = root
        self._parts = parts
        if init:
            self._init()
        return self

    @classmethod
    def _format_parsed_parts(cls, root, parts):
        if root:
            return root + _flavour.join(parts[1:])
        else:
            return _flavour.join(parts)

    def _make_child(self, args):
        root, parts = self._parse_args(args)
        root, parts = _flavour.join_parsed_parts(self._root, self._parts, root, parts)
        return self._from_parsed_parts(root, parts)

    def __str__(self):
        """Return the string representation of the node, suitable for
        passing to system calls."""
        try:
            return self._str
        except AttributeError:
            self._str = self._format_parsed_parts(self._root, self._parts) or "."
            return self._str

    def __fspath__(self):
        return str(self)

    def __bytes__(self):
        """Return the bytes representation of the node.  This is only
        recommended to use under Unix."""
        return os.fsencode(self)

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, str(self))

    @property
    def _cparts(self):
        try:
            return self._cached_cparts
        except AttributeError:
            self._cached_cparts = _flavour.casefold_parts(self._parts)
            return self._cached_cparts

    def __eq__(self, other):
        if not isinstance(other, Node):
            raise NotImplementedError
        return self._cparts == other._cparts

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            self._hash = hash(tuple(self._cparts))
            return self._hash

    def __lt__(self, other):
        if not isinstance(other, Node):
            raise NotImplementedError
        return self._cparts < other._cparts

    def __le__(self, other):
        if not isinstance(other, Node):
            raise NotImplementedError
        return self._cparts <= other._cparts

    def __gt__(self, other):
        if not isinstance(other, Node):
            raise NotImplementedError
        return self._cparts > other._cparts

    def __ge__(self, other):
        if not isinstance(other, Node):
            raise NotImplementedError
        return self._cparts >= other._cparts

    __class_getitem__ = classmethod(GenericAlias)  # noqa

    @property
    def root(self):
        """The root of the node, if any."""
        return self._root

    @property
    def name(self):
        """The final node component, if any."""
        parts = self._parts
        if len(parts) == (1 if self._root else 0):
            return ""
        return parts[-1]

    @property
    def suffix(self):
        """
        The final component's last suffix, if any.

        This includes the leading period. For example: '.txt'
        """
        name = self.name
        i = name.rfind(".")
        if 0 < i < len(name) - 1:
            return name[i:]
        else:
            return ""

    @property
    def suffixes(self):
        """
        A list of the final component's suffixes, if any.

        These include the leading periods. For example: ['.tar', '.gz']
        """
        name = self.name
        if name.endswith("."):
            return []
        name = name.lstrip(".")
        return ["." + suffix for suffix in name.split(".")[1:]]

    @property
    def stem(self):
        """The final node component, minus its last suffix."""
        name = self.name
        i = name.rfind(".")
        if 0 < i < len(name) - 1:
            return name[:i]
        else:
            return name

    def with_name(self, name):
        """Return a new node with the file name changed."""
        if not self.name:
            raise ValueError("%r has an empty name" % (self,))
        root, parts = _flavour.parse_parts((name,))
        if not name or name[-1] in [_flavour.sep, _flavour.altsep] or root or len(parts) != 1:
            raise ValueError("Invalid name %r" % (name))
        return self._from_parsed_parts(self._root, self._parts[:-1] + [name])

    def with_stem(self, stem):
        """Return a new node with the stem changed."""
        return self.with_name(stem + self.suffix)

    def with_suffix(self, suffix):
        """Return a new node with the file suffix changed.  If the node
        has no suffix, add given suffix.  If the given suffix is an empty
        string, remove the suffix from the node.
        """
        f = _flavour
        if f.sep in suffix or f.altsep and f.altsep in suffix:
            raise ValueError("Invalid suffix %r" % (suffix,))
        if suffix and not suffix.startswith(".") or suffix == ".":
            raise ValueError("Invalid suffix %r" % (suffix))
        name = self.name
        if not name:
            raise ValueError("%r has an empty name" % (self,))
        old_suffix = self.suffix
        if not old_suffix:
            name += suffix
        else:
            name = name[: -len(old_suffix)] + suffix
        return self._from_parsed_parts(self._root, self._parts[:-1] + [name])

    def relative_to(self, *other):
        """Return the relative node to another node identified by the passed
        arguments.  If the operation is not possible (because this is not
        a subnode of the other node), raise ValueError.
        """

        if not other:
            raise TypeError("need at least one argument")
        parts = self._parts
        root = self._root
        if root:
            abs_parts = [root] + parts[1:]
        else:
            abs_parts = parts
        to_root, to_parts = self._parse_args(other)
        if to_root:
            to_abs_parts = [to_root] + to_parts[1:]
        else:
            to_abs_parts = to_parts
        n = len(to_abs_parts)
        cf = _flavour.casefold_parts
        if root if n == 0 else cf(abs_parts[:n]) != cf(to_abs_parts):
            formatted = self._format_parsed_parts(to_root, to_parts)
            raise ValueError(
                "{!r} is not in the subnode of {!r}"
                " OR one node is relative and the other is absolute.".format(str(self), str(formatted))
            )
        return self._from_parsed_parts(root if n == 1 else "", abs_parts[n:])

    def is_relative_to(self, *other):
        """Return True if the node is relative to another node or False."""
        try:
            self.relative_to(*other)
            return True
        except ValueError:
            return False

    @property
    def parts(self):
        """An object providing sequence-like access to the
        components in the filesystem node."""
        # We cache the tuple to avoid building a new one each time .parts
        # is accessed.  XXX is this necessary?
        try:
            return self._pparts
        except AttributeError:
            self._pparts = tuple(self._parts)
            return self._pparts

    def joinpath(self, *args):
        """Combine this node with one or several arguments, and return a
        new node representing either a subnode (if all arguments are relative
        nodes) or a totally different node (if one of the arguments is
        anchored).
        """
        return self._make_child(args)

    def __truediv__(self, key):
        try:
            return self._make_child((key,))
        except TypeError:
            raise NotImplementedError

    def __rtruediv__(self, key):
        try:
            return self._from_parts([key] + self._parts)
        except TypeError:
            raise NotImplementedError

    @property
    def parent(self):
        """The logical parent of the node."""
        root = self._root
        parts = self._parts
        if len(parts) == 1 and root:
            return self
        return self._from_parsed_parts(root, parts[:-1])

    @property
    def parents(self):
        """A sequence of this node's logical parents."""
        return _NodeParents(self)

    def is_absolute(self):
        """True if the node is absolute (has both a root and, if applicable,
        a drive)."""
        return bool(self._root)

    def is_reserved(self):
        """Return True if the node contains one of the special names reserved
        by the system, if any."""
        return _flavour.is_reserved(self._parts)

    def match(self, node_pattern):
        """
        Return True if this node matches the given pattern.
        """
        cf = _flavour.casefold
        node_pattern = cf(node_pattern)
        root, pat_parts = _flavour.parse_parts((node_pattern,))
        if not pat_parts:
            raise ValueError("empty pattern")
        if root and root != cf(self._root):
            return False
        parts = self._cparts
        if root:
            if len(pat_parts) != len(parts):
                return False
            pat_parts = pat_parts[1:]
        elif len(pat_parts) > len(parts):
            return False
        for part, pat in zip(reversed(parts), reversed(pat_parts)):
            if not fnmatch.fnmatchcase(part, pat):
                return False
        return True

    def _init(self):
        ...

    def _make_child_relnode(self, part):
        # This is an optimization used for dir walking.  `part` must be
        # a single part relative to this node.
        parts = self._parts + [part]
        return self._from_parsed_parts(self._root, parts)

    # Public API

    def absolute(self):
        """Return an absolute version of this node.  This function works
        even if the node doesn't point to anything.

        No normalization is done, i.e. all '.' and '..' will be kept along.
        Use resolve() to get the canonical node to a file.
        """
        if self.is_absolute():
            return self
        obj = self._from_parts([_get_current()] + self._parts, init=False)
        obj._init()
        return obj

    def resolve(self):
        """
        Make the node absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes under
        Windows).
        """
        s = _flavour.resolve(self)
        normed = posixpath.normpath(s)
        obj = self._from_parts((normed,), init=False)
        obj._init()
        return obj

    def content(self):
        return INDEX_MAP[str(self.absolute())].content

    def samefile(self, other_node):
        """Return whether other_node is the same or not as this file
        (as returned by os.node.samefile()).
        """
        st = self.content()
        try:
            other_st = other_node.content()
        except KeyError:
            return False
        return st == other_st

    def read(self):
        return MappingProxyType(self.content())

    def write(self, content: dict[str, str], create_if_not_exists=False):
        if not self.exists():
            if create_if_not_exists:
                self.touch(content)
            else:
                raise FileNotFoundError(f"No such file or directory: '{self}'")
        if self.is_dir():
            raise IsADirectoryError(f"Is a directory: '{self}'")
        self.content().update(content)

    def touch(self, content: dict[str, str] | None = None, exist_ok=True):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        node = self.absolute()
        if str(node) in INDEX_MAP:
            if not exist_ok:
                raise FileExistsError(f"File exists: '{node}'")
            return self
        if not node.parent.exists():
            raise FileNotFoundError(f"No such file or directory: '{node.parent}'")
        INDEX_MAP[str(node)] = File("file", str(node), content or {})
        CHILD_MAP[str(node.parent)].add(str(node))
        return self

    def mkdir(self, parents=False, exist_ok=False):
        """
        Create a new directory at this given node.
        """
        if self.exists():
            if not exist_ok or not self.is_dir():
                raise FileExistsError(f"File exists: '{self}'")
            return self
        if not self.parent.exists():
            if not parents:
                raise FileNotFoundError(f"No such file or directory: '{self.parent}'")
            self.parent.mkdir(parents=True, exist_ok=True)
        INDEX_MAP[str(self)] = File("dir", str(self), {})
        return self

    def iterdir(self):
        """Iterate over the files in this directory.  Does not yield any
        result for the special nodes '.' and '..'.
        """
        if not self.is_dir():
            raise NotADirectoryError(f"Not a directory: '{self}'")
        for name in CHILD_MAP[str(self)]:
            if name in {".", ".."}:
                # Yielding a node object for these makes little sense
                continue
            yield self._make_child_relnode(name)

    def exists(self):
        """
        Whether this node exists.
        """
        try:
            self.content()
        except KeyError:
            return False
        return True

    def is_dir(self):
        """
        Whether this node is a directory.
        """
        if not self.exists():
            raise FileNotFoundError(f"No such file or directory: '{self}'")
        return INDEX_MAP[str(self.absolute())].isdir

    def is_file(self):
        """
        Whether this node is a regular file (also True for symlinks pointing
        to regular files).
        """
        if not self.exists():
            raise FileNotFoundError(f"No such file or directory: '{self}'")
        return not INDEX_MAP[str(self.absolute())].isdir


ROOT = Node("/")
_CURRENT: "Node" = ROOT


def _get_current():
    return str(_CURRENT)


def _set_current(node: "Node"):
    global _CURRENT
    _CURRENT = node


def mkdir(path: str, base: Node = ROOT, parents: bool = False, exist_ok: bool = False) -> Node:
    return (base / path).mkdir(parents, exist_ok)


def touch(path: str, base: Node = ROOT, content: dict[str, str] | None = None, exist_ok: bool = True) -> Node:
    return (base / path).touch(content, exist_ok)
