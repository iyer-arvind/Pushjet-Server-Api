import rsa
import urllib2
from shared import db
from base64 import b64decode
from json import dumps
from sqlalchemy.dialects.mysql import INTEGER
from datetime import datetime
from config import google_api_key
from models import Subscription, Message

gcm_url = 'https://android.googleapis.com/gcm/send'


class Gcm(db.Model):
    id = db.Column(INTEGER(unsigned=True), primary_key=True)
    uuid = db.Column(db.VARCHAR(40), nullable=False)
    gcmid = db.Column(db.TEXT, nullable=False)
    timestamp_created = db.Column(db.TIMESTAMP, default=datetime.utcnow)

    def __init__(self, device, gcmid):
        self.uuid = device
        self.gcmid = gcmid

    def __repr__(self):
        return '<Gcm %r>' % self.uuid

    def as_dict(self):
        data = {
            "uuid": self.service.as_dict(),
            "gcm_registration_id": self.gcmId,
            "timestamp": int(self.timestamp_created.strftime('%s')),
        }
        return data

    @staticmethod
    def send_message(message):
        """

        :type message: Message
        """
        subscriptions = Subscription.query.filter_by(service=message.service).all()
        if len(subscriptions) == 0:
            return 0
        gcm_filter = Gcm.query.filter(Gcm.uuid.in_([l.device for l in subscriptions])).all()

        devices_plain = [r.gcmid for r in gcm_filter if r.pubkey is None]

        if len(devices_plain) > 0:
            data = {"message": dumps(message.as_dict()), "encrypted": False}
            Gcm.gcm_send(devices_plain, data)

        if len(gcm_filter) > 0:
            uuids = [g.uuid for g in gcm_filter]
            gcm_subscriptions = Subscription.query.filter_by(service=message.service).filter(Subscription.device.in_(uuids)).all()
            last_message = Message.query.order_by(Message.id.desc()).first()
            for l in gcm_subscriptions:
                l.timestamp_checked = datetime.utcnow()
                l.last_read = last_message.last_read if last_message else 0
            db.session.commit()
        return len(gcm_filter)

    @staticmethod
    def gcm_send(ids, data):
        data = dumps({
            "registration_ids": ids,
            "data": data,
        })
        headers = {
            'Authorization': 'key=%s' % google_api_key,
            'Content-Type': 'application/json',
        }
        req = urllib2.Request('https://android.googleapis.com/gcm/send', data, headers)
        urllib2.urlopen(req).read()
