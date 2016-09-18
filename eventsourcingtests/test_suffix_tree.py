# coding=utf-8
from uuid import uuid4

from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty
from eventsourcing.domain.model.events import publish


def register_new_node():
    node_id = uuid4().hex
    event = Node.Created(entity_id=node_id)
    entity = Node.mutate(event=event)
    publish(event)
    return entity


def make_edge_id(source_node_index, first_char):
    return "{}::{}".format(source_node_index, first_char)


def register_new_edge(edge_id, first_char_index, last_char_index, source_node_id, dest_node_id):
    event = Edge.Created(
        entity_id=edge_id,
        first_char_index=first_char_index,
        last_char_index=last_char_index,
        source_node_id=source_node_id,
        dest_node_id=dest_node_id,
    )
    entity = Edge.mutate(event=event)
    publish(event)
    return entity


def register_new_suffix_tree(string, case_insensitive=False):
    suffix_tree_id = uuid4().hex
    event = SuffixTree.Created(
        entity_id=suffix_tree_id,
        string=string,
        case_insensitive=case_insensitive,
    )
    entity = SuffixTree.mutate(event=event)
    publish(event)
    return entity


class Node(EventSourcedEntity):
    """A node in the suffix tree.

    suffix_node_id
        the id of a node with a matching suffix, representing a suffix link.
        None indicates this node has no suffix link.
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    def __init__(self, *args, **kwargs):
        super(Node, self).__init__(*args, **kwargs)
        self._suffix_node_id = None

    @mutableproperty
    def suffix_node_id(self):
        return self._suffix_node_id

    def __repr__(self):
        return "Node(suffix link: %d)" % self.suffix_node_id


class Edge(EventSourcedEntity):
    """An edge in the suffix tree.

    first_char_index
        index of start of string part represented by this edge

    last_char_index
        index of end of string part represented by this edge

    source_node_id
        id of source node of edge

    dest_node_id
        id of destination node of edge
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    def __init__(self, first_char_index, last_char_index, source_node_id, dest_node_id, **kwargs):
        super(Edge, self).__init__(**kwargs)
        self._first_char_index = first_char_index
        self._last_char_index = last_char_index
        self._source_node_id = source_node_id
        self._dest_node_id = dest_node_id

    @mutableproperty
    def first_char_index(self):
        return self._first_char_index

    @property
    def last_char_index(self):
        return self._last_char_index

    @mutableproperty
    def source_node_id(self):
        return self._source_node_id

    @property
    def dest_node_id(self):
        return self._dest_node_id

    @property
    def length(self):
        return self.last_char_index - self.first_char_index

    def __repr__(self):
        return 'Edge(%d, %d, %d, %d)' % (self.source_node_id, self.dest_node_id
                                         , self.first_char_index, self.last_char_index)


class Suffix(object):
    """Represents a suffix from first_char_index to last_char_index.

    source_node_id
        index of node where this suffix starts

    first_char_index
        index of start of suffix in string

    last_char_index
        index of end of suffix in string
    """

    def __init__(self, source_node_id, first_char_index, last_char_index):
        self.source_node_id = source_node_id
        self.first_char_index = first_char_index
        self.last_char_index = last_char_index

    @property
    def length(self):
        return self.last_char_index - self.first_char_index

    def explicit(self):
        """A suffix is explicit if it ends on a node. first_char_index
        is set greater than last_char_index to indicate this.
        """
        return self.first_char_index > self.last_char_index

    def implicit(self):
        return self.last_char_index >= self.first_char_index


class SuffixTree(EventSourcedEntity):
    """A suffix tree for string matching. Uses Ukkonen's algorithm
    for construction.
    """

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    def __init__(self, string, case_insensitive=False, **kwargs):
        """
        string
            the string for which to construct a suffix tree
        """
        super(SuffixTree, self).__init__(**kwargs)
        self._string = string
        self._case_insensitive = case_insensitive
        self._N = len(string) - 1
        node = register_new_node()
        self._nodes = {node.id: node}
        self._root_node_id = node.id
        self._edges = {}
        self._active = Suffix(self._root_node_id, 0, -1)
        if self._case_insensitive:
            self._string = self._string.lower()
        for i in range(len(string)):
            self._add_prefix(i)

    @property
    def string(self):
        return self._string

    @property
    def N(self):
        return self._N

    @property
    def nodes(self):
        return self._nodes

    @property
    def edges(self):
        return self._edges

    @property
    def activate(self):
        return self._active

    @property
    def case_insensitive(self):
        return self._case_insensitive

    @property
    def active(self):
        return self._active

    def __repr__(self):
        """
        Lists edges in the suffix tree
        """
        curr_index = self.N
        s = "\tStart \tEnd \tSuf \tFirst \tLast \tString\n"
        values = self.edges.values()
        values.sort(key=lambda x: x.source_node_id)
        for edge in values:
            if edge.source_node_id == None:
                continue
            s += "\t%s \t%s \t%s \t%s \t%s \t" % (edge.source_node_id
                                                  , edge.dest_node_id
                                                  , self.nodes[edge.dest_node_id].suffix_node_id
                                                  , edge.first_char_index
                                                  , edge.last_char_index)

            top = min(curr_index, edge.last_char_index)
            s += self.string[edge.first_char_index:top + 1] + "\n"
        return s

    def _add_prefix(self, last_char_index):
        """The core construction method.
        """
        last_parent_node_id = None
        while True:
            parent_node_id = self.active.source_node_id
            if self.active.explicit():
                edge_id = make_edge_id(self.active.source_node_id, self.string[last_char_index])
                if edge_id in self.edges:
                    # prefix is already in tree
                    break
            else:
                edge_id = make_edge_id(self.active.source_node_id, self.string[self.active.first_char_index])
                e = self.edges[edge_id]
                if self.string[e.first_char_index + self.active.length + 1] == self.string[last_char_index]:
                    # prefix is already in tree
                    break
                parent_node_id = self._split_edge(e, self.active)

            node = register_new_node()
            self.nodes[node.id] = node
            edge_id = make_edge_id(last_char_index, self.string[last_char_index])
            e = register_new_edge(
                edge_id=edge_id,
                first_char_index=last_char_index,
                last_char_index=self.N,
                source_node_id=parent_node_id,
                dest_node_id=node.id,
            )
            self._insert_edge(e)

            if last_parent_node_id is not None:
                self.nodes[last_parent_node_id].suffix_node_id = parent_node_id
            last_parent_node_id = parent_node_id

            if self.active.source_node_id == self._root_node_id:
                self.active.first_char_index += 1
            else:
                self.active.source_node_id = self.nodes[self.active.source_node_id].suffix_node_id
            self._canonize_suffix(self.active)
        if last_parent_node_id is not None:
            self.nodes[last_parent_node_id].suffix_node_id = parent_node_id
        self.active.last_char_index += 1
        self._canonize_suffix(self.active)

    def _insert_edge(self, edge):
        edge_id = make_edge_id(edge.source_node_id, self.string[edge.first_char_index])
        self.edges[edge_id] = edge

    def _remove_edge(self, edge):
        edge_id = make_edge_id(edge.source_node_id, self.string[edge.first_char_index])
        self.edges.pop(edge_id)

    def _split_edge(self, edge, suffix):
        node = register_new_node()
        self.nodes[node.id] = node
        edge_id = make_edge_id(edge.first_char_index, self.string[edge.first_char_index])
        e = register_new_edge(
            edge_id=edge_id,
            first_char_index=edge.first_char_index,
            last_char_index=edge.first_char_index + suffix.length,
            source_node_id=suffix.source_node_id,
            dest_node_id=node.id,
        )

        self._remove_edge(edge)
        self._insert_edge(e)
        self.nodes[e.dest_node_id].suffix_node_id = suffix.source_node_id  ### need to add node for each edge
        edge.first_char_index += suffix.length + 1
        edge.source_node_id = e.dest_node_id
        self._insert_edge(edge)
        return e.dest_node_id

    def _canonize_suffix(self, suffix):
        """This canonizes the suffix, walking along its suffix string until it
        is explicit or there are no more matched nodes.
        """
        if not suffix.explicit():
            edge_id = make_edge_id(suffix.source_node_id, self.string[suffix.first_char_index])
            e = self.edges[edge_id]
            if e.length <= suffix.length:
                suffix.first_char_index += e.length + 1
                suffix.source_node_id = e.dest_node_id
                self._canonize_suffix(suffix)

    # Public methods
    def find_substring(self, substring):
        """Returns the index of substring in string or -1 if it
        is not found.
        """
        if not substring:
            return -1
        if self.case_insensitive:
            substring = substring.lower()
        curr_node_id = self._root_node_id
        i = 0
        while i < len(substring):
            edge_id = make_edge_id(curr_node_id, substring[i])
            edge = self.edges.get(edge_id)
            if not edge:
                return -1
            ln = min(edge.length + 1, len(substring) - i)
            if substring[i:i + ln] != self.string[edge.first_char_index:edge.first_char_index + ln]:
                return -1
            i += edge.length + 1
            curr_node_id = edge.dest_node_id
        return edge.first_char_index - len(substring) + ln

    def has_substring(self, substring):
        return self.find_substring(substring) != -1


import unittest


class SuffixTreeTest(unittest.TestCase):
    """Some functional tests.
    """

    def test_empty_string(self):
        st = register_new_suffix_tree('')
        self.assertEqual(st.find_substring('not there'), -1)
        self.assertEqual(st.find_substring(''), -1)
        self.assertFalse(st.has_substring('not there'))
        self.assertFalse(st.has_substring(''))

    def test_repeated_string(self):
        st = register_new_suffix_tree("aaa")
        self.assertEqual(st.find_substring('a'), 0)
        self.assertEqual(st.find_substring('aa'), 0)
        self.assertEqual(st.find_substring('aaa'), 0)
        self.assertEqual(st.find_substring('b'), -1)
        self.assertTrue(st.has_substring('a'))
        self.assertTrue(st.has_substring('aa'))
        self.assertTrue(st.has_substring('aaa'))

        self.assertFalse(st.has_substring('aaaa'))
        self.assertFalse(st.has_substring('b'))
        # case sensitive by default
        self.assertFalse(st.has_substring('A'))

    def test_long_string(self):
        f = open("test.txt")
        st = register_new_suffix_tree(f.read())
        self.assertEqual(st.find_substring('Ukkonen'), 1498)
        self.assertEqual(st.find_substring('Optimal'), 11074)
        self.assertFalse(st.has_substring('ukkonen'))

    def test_case_sensitivity(self):
        f = open("test.txt")
        st = register_new_suffix_tree(f.read(), case_insensitive=True)
        self.assertEqual(st.find_substring('ukkonen'), 1498)
        self.assertEqual(st.find_substring('Optimal'), 1830)

        # def test_repr(self):
        #     st = SuffixTree("t")
        #     output = '\tStart \tEnd \tSuf \tFirst \tLast \tString\n\t0 \t1 \t-1 \t0 \t0 \tt\n'
        #     # import pdb;
        #     # pdb.set_trace()
        #     self.assertEqual(st.__repr__(), output)
