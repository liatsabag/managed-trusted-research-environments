"""Integration tests for API v1 endpoint controllers."""

import asyncio
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Defensive shim for environments where anyio subdependency is not installed
class AnyioMock(ModuleType):
    def __getattr__(self, name):
        return MagicMock

for mod_name in ["anyio", "anyio.abc", "anyio.to_thread", "anyio.lowlevel"]:
    if mod_name not in sys.modules:
        m = AnyioMock(mod_name)
        m.ObjectReceiveStream = MagicMock
        m.ObjectSendStream = MagicMock
        m.CapacityLimiter = MagicMock
        m.to_thread = MagicMock()
        sys.modules[mod_name] = m

import unittest
from backend.app.api.v1.institutes import list_institutes
from backend.app.api.v1.rooms import (
    downgrade_room,
    get_fleet_service,
    get_room,
    get_room_packages,
    list_rooms,
    reactivate_room,
)
from backend.app.models.rooms import DowngradeRequest


class TestAPIv1Controllers(unittest.TestCase):
    """Test suite for API v1 endpoint controller functions."""

    @classmethod
    def setUpClass(cls):
        service = get_fleet_service()
        mock_crm = MagicMock()
        mock_req = MagicMock()
        mock_req.execute.return_value = {"bindings": []}
        mock_crm.projects().getIamPolicy.return_value = mock_req
        mock_crm.projects().setIamPolicy.return_value = mock_req
        service._crm_client = mock_crm

    def test_rooms_list_controller(self):
        """Verify list_rooms controller returns 4 room summaries."""
        service = get_fleet_service()
        rooms = asyncio.run(list_rooms(service=service))
        self.assertEqual(len(rooms), 4)
        room_ids = [r.room_id for r in rooms]
        self.assertIn("rr-oncology-01", room_ids)

    def test_room_detail_controller(self):
        """Verify get_room controller returns complete room detail."""
        service = get_fleet_service()
        room = asyncio.run(get_room("rr-oncology-01", service=service))
        self.assertEqual(room.room_id, "rr-oncology-01")
        self.assertEqual(len(room.researchers), 2)

    def test_room_packages_controller(self):
        """Verify get_room_packages controller."""
        service = get_fleet_service()
        packages = asyncio.run(get_room_packages("rr-oncology-01", service=service))
        self.assertGreater(len(packages), 0)

    def test_room_downgrade_and_reactivate_controller(self):
        """Verify IAM downgrade and reactivation lifecycle controllers."""
        service = get_fleet_service()
        down_req = DowngradeRequest(reason="DUA expiration check")
        down_res = asyncio.run(downgrade_room("rr-oncology-01", down_req, service=service))
        self.assertEqual(down_res.action.lower(), "downgrade")
        self.assertEqual(down_res.room_id, "rr-oncology-01")

        react_res = asyncio.run(reactivate_room("rr-oncology-01", service=service))
        self.assertEqual(react_res.action.lower(), "reactivate")
        self.assertEqual(react_res.room_id, "rr-oncology-01")

    def test_institutes_list_controller(self):
        """Verify list_institutes controller returns 4 institutes."""
        service = get_fleet_service()
        institutes = asyncio.run(list_institutes(service=service))
        self.assertEqual(len(institutes), 4)


if __name__ == "__main__":
    unittest.main()
