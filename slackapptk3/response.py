#  Copyright 2019 Jeremy Schulman, nwkautomaniac@gmail.com
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


from slackapptk3.messenger import Messenger
from slackapptk3.request.any import AnyRequest

__all__ = ["AnyRequest", "Response", "Messenger"]


class Response(Messenger):
    def __init__(self, rqst: AnyRequest):
        super(Response, self).__init__(
            app=rqst.app, channel=rqst.channel, response_url=rqst.response_url
        )

        self.rqst = rqst

    async def delete_origin(self):
        """
        Delete the originating Slack message.
        """
        await self.client.chat_delete(
            channel=self.rqst.channel, ts=self.rqst.rqst_data["message"]["ts"]
        )
