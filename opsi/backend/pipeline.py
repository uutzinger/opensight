from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional, Set, Type
from uuid import UUID

from .manager import Manager
from .manager_schema import Function


class Link:
    def run(self):
        raise NotImplementedError


# Map inputname -> (output_node, output_name)
class Connection(NamedTuple):
    id: UUID
    name: str


Links = Dict[str, Connection]


@dataclass(frozen=True)
class StaticLink(Link):
    value: Any

    def run(self):
        return self.value


class Node:
    def __init__(self, func: Type[Function], id: UUID):
        self.func: Optional[Function] = None
        self.func_type = func
        self.id = id

        self.settings = None
        self.next_frame()
        self.reset_io()

    def next_frame(self):
        self.results: Optional[self.func_type.Outputs] = None
        self.has_run: bool = False

    def reset_io(self):
        self.inputLinks: Dict[str, Optional[Link]] = {
            name: StaticLink(None) for name in self.func_type.InputTypes.keys()
        }

    def ensure_init(self):
        if self.func is not None:
            return

        self.func = self.func_type(self.settings)

    def dispose(self):
        if self.func is None:
            return

        self.func.dispose()
        self.func = None

    def set_staticlink(self, key: str, item: Any):
        self.inputLinks[key] = StaticLink(item)

    def set_staticlinks(self, vals: Dict[str, Any]):
        for key, item in vals.items():
            self.set_staticlink(key, item)

    def run(self):
        if self.has_run:
            return self.results

        self.ensure_init()

        inputs = {name: link.run() for name, link in self.inputLinks.items()}
        inputs = self.func_type.Inputs(**inputs)

        self.results = self.func.run(inputs)
        self.has_run = True

        return self.results


class Pipeline:
    def __init__(self):
        self.nodes: Dict[UUID, Node] = {}
        self.links: List[Link] = []
        self.entrynodes: Set[UUID] = set()

    def run(self):
        for node in self.nodes.values():
            node.next_frame()

        self._run()

    def _run(self):
        raise NotImplementedError

    def create_node(self, func: Type[Function], id: UUID):
        """
        The caller is responsible for calling
        pipeline.create_links(node, ...) and node.set_staticlinks(...),
        and setting node.settings as appropriate
        """
        self.nodes[id] = Node(func, id)

        if self.nodes[id].func_type.has_sideeffect:
            self.entrynodes.add(id)

        return self.nodes[id]

    def create_links(self, input_node_id, links: Links):
        input_node = self.nodes[input_node_id]

        for input_name, conn in links.items():
            output_node = self.nodes[conn.id]

            link = self._create_link(input_node, input_name, output_node, conn.name)

            input_node.inputLinks[input_name] = link
            self.links.append(link)

    def _create_link(self, input_node, input_name, output_node, output_name) -> Link:
        raise NotImplementedError

    def prune_nodetree(self, new_node_ids):
        old_node_ids = set(self.nodes.keys())
        new_node_ids = set(new_node_ids)

        # clear existing links

        self.links = []

        for node in self.nodes.values():
            node.reset_io()

        # remove deleted nodes

        for id in old_node_ids - new_node_ids:
            self.nodes[id].dispose()

            del self.nodes[id]
            self.entrynodes.discard(id)