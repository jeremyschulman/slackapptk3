from typing import Callable, Optional
from enum import IntEnum, auto

# from slack_sdk.models.blocks.basic_components import PlainTextObject
from slackapptk3.request.any import AnyRequest
from slackapptk3.web.classes.view import View
from slackapptk3.errors import SlackAppTKError
from slackapptk3.app import SlackApp

__all__ = ["Modal", "ModalMode", "View"]


def with_callback(meth):
    def wrapper(self, *args, callback: Callable = None, **kwargs):
        cbk = callback or self.callback
        if cbk:
            self.app.ic.view.on(self.view.callback_id, cbk)

        if self.notify_on_close:
            self.view.notify_on_close = True
            self.app.ic.view_closed.on(self.view.callback_id, self.notify_on_close)

        return meth(self, *args, **kwargs)

    return wrapper


class ModalMode(IntEnum):  # noqa
    OPEN = auto()
    PUSH = auto()
    UPDATE = auto()


class Modal(object):
    def __init__(
        self,
        rqst: AnyRequest,
        view: Optional[View] = None,
        detached: Optional[bool] = False,
        callback: Optional[Callable] = None,
    ):
        """

        Parameters
        ----------
        rqst : Request
            The originating request that this Modal will be bound to.
            If this request contains a view attribute it means that the
            request was a result of a view_* interactive response, for
            example view_submission.  This rqst.view will then become
            the basis for the Modal.view

        view : View
            If provided will be the basis of the Modal view instance.

        detached : bool
            If this Modal is being used outside the context of the Slack
            general process, for example running in a backthrough Thread,
            then set this to True so that the methods operating on the
            modal, for example update(), execute as required.
        """
        self.rqst = rqst
        self.app: SlackApp = rqst.app

        def from_payload_or_new():
            if "view" in rqst.rqst_data:
                return View.from_view(rqst.rqst_data["view"])
            return View(type="modal")

        if view and not isinstance(view, View):
            raise SlackAppTKError("caller provided view not of View origin")

        self.view = view or from_payload_or_new()
        self.detached = detached
        self.callback = callback
        self.notify_on_close = None

        # by default, when "calling show", use the modal open.  The Caller can
        # change this to open methods so that they can invoke show without
        # having to know which mode to use.

        self.show = self.open

    @with_callback
    async def open(self):
        return await self.rqst.client.views_open(
            trigger_id=self.rqst.trigger_id, view=self.view.to_dict()
        )

    @with_callback
    async def update(self):
        if self.rqst.rqst_type == "view_submission" and not self.detached:
            return {"response_action": "update", "view": self.view.to_dict()}

        if hasattr(self.view, "view_id"):
            kwargs = dict(view=self.view.to_dict(), view_id=self.view.view_id)

            if not self.detached:
                kwargs["hash"] = self.view.view_hash

            return await self.rqst.client.views_update(**kwargs)

        raise SlackAppTKError("Attempting to update view in unknown context")

    @with_callback
    async def push(self):
        if self.rqst.rqst_type == "view_submission":
            return {"response_action": "push", "view": self.view.to_dict()}

        return await self.rqst.client.views_push(
            trigger_id=self.rqst.trigger_id, view=self.view.to_dict()
        )
