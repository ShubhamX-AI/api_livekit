# Tools

## Overview

Tools extend assistant capabilities by executing either webhook calls or static-return actions during a conversation.

## Execution Types

| Type | Description | Typical Use |
| :--- | :--- | :--- |
| `webhook` | Executes an HTTP POST to an external endpoint. | Fetch live data or trigger external systems. |
| `static` | Returns a fixed payload without external HTTP. | Constant answers such as support hours or policy text. |

## Endpoints

- [Create Tool](create.md)
- [List Tools](list.md)
- [Get Tool Details](get.md)
- [Update Tool](update.md)
- [Delete Tool](delete.md)
- [Attach Tools](attach.md)
- [Detach Tools](detach.md)
- [Webhook Payload Format](webhook.md)
- [Design Guidelines](design.md)
