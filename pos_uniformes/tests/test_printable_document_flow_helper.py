from __future__ import annotations

from contextlib import contextmanager
import unittest

from pos_uniformes.services.sale_document_view_service import PrintableDocumentView
from pos_uniformes.ui.helpers.printable_document_flow_helper import open_printable_document_flow


class PrintableDocumentFlowHelperTests(unittest.TestCase):
    def test_open_printable_document_flow_loads_document_and_opens_dialog(self) -> None:
        parent = object()
        events: list[str] = []

        @contextmanager
        def fake_session_factory():
            events.append("session-open")
            yield "session"
            events.append("session-close")

        def build_document_view(session):
            self.assertEqual(session, "session")
            events.append("build-view")
            return PrintableDocumentView(title="Ticket 10", content="contenido")

        opened: list[tuple[object, str, str]] = []

        def open_dialog(current_parent, title, content):
            opened.append((current_parent, title, content))
            events.append("open-dialog")

        view = open_printable_document_flow(
            parent=parent,
            session_factory=fake_session_factory,
            build_document_view=build_document_view,
            open_dialog=open_dialog,
        )

        self.assertEqual(view.title, "Ticket 10")
        self.assertEqual(view.content, "contenido")
        self.assertEqual(opened, [(parent, "Ticket 10", "contenido")])
        self.assertEqual(events, ["session-open", "build-view", "session-close", "open-dialog"])


if __name__ == "__main__":
    unittest.main()
