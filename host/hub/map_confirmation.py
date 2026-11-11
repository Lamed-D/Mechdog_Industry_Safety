"""Confirm a hash-bound cloud draft; never activate a configuration or move a robot."""
from datetime import datetime, timezone
from host.hub.config_sync import grid_file
from host.hub.store import CONFIG_LIMIT, encode
from host.map_review import approve_edit
import json


class MapConfirmer:
    def __init__(self, store, metadata, fetch, *, wall, clock_trusted, authorize):
        self.store, self.metadata, self.fetch = store, metadata, fetch
        self.wall, self.clock_trusted, self.authorize = wall, clock_trusted, authorize

    def __call__(self, command):
        if command.kind != 'map_confirm' or command.hub_id != self.store.hub_id:
            raise ValueError('map confirmation command required')
        payload = dict(command.payload)
        rows = []
        for name in ('base','proposal'):
            key = payload[name+'_map_id']
            row = json.loads(encode(self.metadata(key),CONFIG_LIMIT))
            if (row['id'] != key or row['hub_id'] != self.store.hub_id
                    or row['sha256'] != payload[name+'_sha256']
                    or row['state'] not in ('draft','confirmed')
                    or type(row['version']) is not int or row['version']<1):
                raise ValueError('map changed since human review')
            rows.append(row)
        base, proposal = rows
        if proposal['state'] != 'draft' or proposal['version']<=base['version']:
            raise ValueError('newer draft required')
        base_grid, proposal_grid = (grid_file(row,self.fetch) for row in rows)
        approve_edit(base_grid,proposal_grid,expected_base_digest=base_grid.digest(),
                     expected_proposal_digest=proposal_grid.digest(),
                     approved_clearings=payload['approved_clearings'])
        # Downloads may have taken longer than the command lifetime. Reauthorize now.
        now = self.wall()
        if (self.clock_trusted() is not True or not command.created_at <= now < command.expires_at
                or 'map_confirm' not in self.authorize(command.device_id)):
            raise ValueError('confirmation expired or permission revoked')
        proposal.update(state='confirmed',device_id=self.store.device_id,
            confirmed_by=command.device_id,
            confirmed_at=datetime.fromtimestamp(now,timezone.utc).isoformat().replace('+00:00','Z'),
            base_sha256=base['sha256'],approved_clearings=list(payload['approved_clearings']))
        if not self.store.enqueue('maps',proposal):
            raise ValueError('confirmation outbox unavailable')
