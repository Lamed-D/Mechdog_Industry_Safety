"""Memory-only gateway; synthetic tests, not an RLS or SQL emulator."""
from copy import deepcopy


class FakeSupabase:
    def __init__(self):
        self.rows = {}
        self.pending = []
        self.uploads = []
        self.offline = False
        self.fail_after_write = False

    def upload(self, item):
        if self.offline:
            raise ConnectionError('synthetic offline')
        self.rows[item.table, item.row['id']] = deepcopy(item.row)
        self.uploads.append(item.event_id)
        if self.fail_after_write:
            raise ConnectionError('synthetic lost acknowledgement')

    def commands(self, hub_id):
        if self.offline:
            raise ConnectionError('synthetic offline')
        rows = [deepcopy(row) for row in self.pending if row['hub_id'] == hub_id]
        stops = [row for row in rows if row['kind'] == 'estop'][:100]
        normal = [row for row in rows if row['kind'] != 'estop'][:100]
        return stops + normal
