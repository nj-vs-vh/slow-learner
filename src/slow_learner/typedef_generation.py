import collections
import keyword
import random
import re
import string
from enum import IntEnum

from .learnt_types import (
    LCollection,
    LearntType,
    LLiteral,
    LMapping,
    LMissingTypedDictKey,
    LNone,
    LTuple,
    LType,
    LTypedDict,
    LUnion,
)


class PythonVersion(IntEnum):
    PY38 = 8
    PY39 = 9
    PY310 = 10
    PY311 = 11


def capitalize_first_letter(s: str) -> str:
    if s:
        return s[0].capitalize() + s[1:]
    else:
        return s


def new_type_name(name: str, dependency_typedefs: dict[str, str]) -> str:
    name = "".join([capitalize_first_letter(m.group()) for m in re.finditer(r"[A-Za-z0-9]+", name)])
    if not name.isidentifier():
        name = "_" + name
    if not name.isidentifier():
        name = "GeneratedType"
    if name not in dependency_typedefs:
        return name
    while True:
        name += random.choice(string.ascii_uppercase)
        if name not in dependency_typedefs:
            return name


def generate_typedef_rhs(
    lt: LearntType,
    type_name: str,
    target_version: PythonVersion,
    imports: set[tuple[str, str]],
    dependency_typedefs: dict[str, str],
) -> str:
    # preprocessing types before typedef generation
    # demoting empty typed dict to dict[Any, Any]
    if isinstance(lt, LTypedDict) and not lt.fields:
        lt = LMapping(dict, key_type=LUnion([]), value_type=LUnion([]))

    # generating types
    if isinstance(lt, (LNone, LType)):
        return str(lt)
    elif isinstance(lt, LLiteral):
        imports.add(("typing", "Literal"))
        return str(lt)
    elif isinstance(lt, LUnion):
        if not lt.member_types:
            # empty union translates to Any type, but only when generating the code
            imports.add(("typing", "Any"))
            return "Any"
        non_none_member_types = [m for m in lt.member_types if not isinstance(m, LNone)]
        if not non_none_member_types:
            return str(LNone())
        member_types_in_body = lt.member_types if target_version >= PythonVersion.PY310 else non_none_member_types
        if len(member_types_in_body) > 1:
            member_typedefs_in_body = [
                generate_typedef_rhs(
                    member_lt,
                    new_type_name(type_name + f"Variant{member_idx + 1}", dependency_typedefs),
                    target_version,
                    imports,
                    dependency_typedefs,
                )
                for member_idx, member_lt in enumerate(member_types_in_body)
            ]
        else:
            member_typedefs_in_body = [
                generate_typedef_rhs(
                    member_types_in_body[0],
                    new_type_name(type_name, dependency_typedefs),
                    target_version,
                    imports,
                    dependency_typedefs,
                )
            ]
        if target_version >= PythonVersion.PY310:
            union_body = " | ".join(member_typedefs_in_body)
        else:
            imports.add(("typing", "Union"))
            union_body = (
                "Union[" + ", ".join(member_typedefs_in_body) + "]"
                if len(member_typedefs_in_body) > 1
                else member_typedefs_in_body[0]
            )
            if non_none_member_types != lt.member_types:
                imports.add(("typing", "Optional"))
                return "Optional[" + union_body + "]"
            else:
                return union_body
    elif isinstance(lt, LTuple):
        if target_version >= PythonVersion.PY39:
            tuple_type = "tuple"
        else:
            imports.add(("typing", "Tuple"))
            tuple_type = "Tuple"
        return (
            tuple_type
            + "["
            + ", ".join(
                generate_typedef_rhs(
                    item_lt,
                    new_type_name(type_name + f"Item{item_idx}", dependency_typedefs),
                    target_version,
                    imports,
                    dependency_typedefs,
                )
                for item_idx, item_lt in enumerate(lt.item_types)
            )
            + "]"
        )
    elif isinstance(lt, LCollection):
        if target_version >= PythonVersion.PY39 and hasattr(lt.collection_type, "__class_getitem__"):
            # i.e. the type is a generic, see https://docs.python.org/3/library/stdtypes.html#generic-alias-type
            if lt.collection_type.__module__ != "builtins":
                imports.add((lt.collection_type.__module__, lt.collection_type.__name__))
            collection_typedef = lt.collection_type.__name__
        else:
            collection_typedef = {list: "List", set: "Set", frozenset: "FrozenSet", collections.deque: "Deque"}.get(
                lt.collection_type, "Collection"
            )
            module = (
                "collections.abc"
                if target_version > PythonVersion.PY39 and collection_typedef == "Collection"
                else "typing"
            )
            imports.add((module, collection_typedef))
        item_typedef = generate_typedef_rhs(
            lt.item_type,
            new_type_name(type_name + "Item", dependency_typedefs),
            target_version,
            imports,
            dependency_typedefs,
        )
        return f"{collection_typedef}[{item_typedef}]"
    elif isinstance(lt, LMapping):
        if target_version >= PythonVersion.PY39 and hasattr(lt.mapping_type, "__class_getitem__"):
            # i.e. the type is a generic, see https://docs.python.org/3/library/stdtypes.html#generic-alias-type
            if lt.mapping_type.__module__ != "builtins":
                imports.add((lt.mapping_type.__module__, lt.mapping_type.__name__))
            mapping_typedef = lt.mapping_type.__name__
        else:
            mapping_typedef = {
                dict: "Dict",
                collections.defaultdict: "DefaultDict",
                collections.OrderedDict: "OrderedDict",
                collections.ChainMap: "ChainMap",
            }.get(lt.mapping_type, "Mapping")
            module = (
                "collections.abc" if target_version > PythonVersion.PY39 and mapping_typedef != "Dict" else "typing"
            )
            imports.add((module, mapping_typedef))
        key_typedef = generate_typedef_rhs(
            lt.key_type,
            new_type_name(type_name + "Key", dependency_typedefs),
            target_version,
            imports,
            dependency_typedefs,
        )
        value_typedef = generate_typedef_rhs(
            lt.value_type,
            new_type_name(type_name + "Value", dependency_typedefs),
            target_version,
            imports,
            dependency_typedefs,
        )
        return f"{mapping_typedef}[{key_typedef}, {value_typedef}]"
    elif isinstance(lt, LTypedDict):
        imports.add(("typing", "TypedDict"))
        not_required_keys: set[str] = set()
        field_types_to_generate: dict[str, LearntType] = dict()
        for key, value_lt in lt.fields.items():
            if isinstance(value_lt, LUnion):
                non_missing_members = [
                    mlt for mlt in value_lt.member_types if not isinstance(mlt, LMissingTypedDictKey)
                ]
                if non_missing_members == value_lt.member_types:
                    field_types_to_generate[key] = value_lt
                else:
                    field_types_to_generate[key] = LUnion(non_missing_members)
                    not_required_keys.add(key)
            else:
                field_types_to_generate[key] = value_lt

        use_class_notation = all(
            key.isidentifier() and not keyword.iskeyword(key) and not keyword.issoftkeyword(key)
            for key in field_types_to_generate
        )
        use_total_false = False
        if not_required_keys:
            if not_required_keys == set(field_types_to_generate.keys()):
                use_total_false = True
            else:
                module = "typing" if target_version >= PythonVersion.PY311 else "typing_extensions"
                imports.add((module, "NotRequired"))
        typed_dict_def_lines: list[str] = []

        field_typedefs: dict[str, str] = dict()
        for key, value_lt in field_types_to_generate.items():
            value_typedef = generate_typedef_rhs(
                value_lt,
                new_type_name(type_name + (key.capitalize() or "EmptyKey"), dependency_typedefs),
                target_version,
                imports,
                dependency_typedefs,
            )
            if key in not_required_keys and not use_total_false:
                value_typedef = f"NotRequired[{value_typedef}]"
            field_typedefs[key] = value_typedef

        if use_class_notation:
            inheritance_args = ", total=False" if use_total_false else ""
            typed_dict_def_lines.append(f"class {type_name}(TypedDict{inheritance_args}):")
            for key, value_typedef in field_typedefs.items():
                typed_dict_def_lines.append(f"    {key}: {value_typedef}")
        else:
            fields_arg = "{"
            for key, value_typedef in field_typedefs.items():
                fields_arg += f"{key!r}: {value_typedef}, "
            fields_arg += "}"
            args = [repr(type_name), fields_arg]
            if use_total_false:
                args.append("total=False")
            typed_dict_def_lines = [f"{type_name} = TypedDict(" + ", ".join(args) + ")"]
        dependency_typedefs[type_name] = "\n".join(typed_dict_def_lines)
        return type_name

    raise RuntimeError(f"Can't generate typedef RHS for {lt}, python version {target_version}")
