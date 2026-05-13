from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import executors, serializers
from .auth import AdminJWTAuthentication, current_agent, issue_admin_token, issue_token
from .models import (
    Action,
    Agent,
    ApprovalTicket,
    AuditLog,
    PermissionOverride,
    Toolkit,
)
from .permissions_resolver import resolve


class TokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response({"error": "agent_id required"}, status=400)
        try:
            agent = Agent.objects.get(id=agent_id, is_active=True)
        except (Agent.DoesNotExist, ValueError):
            return Response({"error": "unknown or inactive agent"}, status=404)
        return Response(issue_token(agent))


class AdminTokenView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        return Response(issue_admin_token(request.user))


class ToolkitListView(APIView):
    def get(self, request):
        toolkits = Toolkit.objects.all().order_by("slug")
        data = serializers.ToolkitSerializer(toolkits, many=True).data
        return Response({"toolkits": data})


class ActionListView(APIView):
    def get(self, request, toolkit):
        tk = get_object_or_404(Toolkit, slug=toolkit)
        actions = tk.actions.all().order_by("slug")
        ctx = {"resolver": resolve, "agent": current_agent(request)}
        data = serializers.ActionSerializer(actions, many=True, context=ctx).data
        return Response({"toolkit": tk.slug, "actions": data})


class ActionSchemaView(APIView):
    def get(self, request, toolkit, action):
        act = get_object_or_404(Action, toolkit__slug=toolkit, slug=action)
        return Response(
            {
                "toolkit": toolkit,
                "action": action,
                "input_schema": act.input_schema,
                "output_schema": act.output_schema,
            }
        )


class CallActionView(APIView):
    def post(self, request, toolkit, action):
        try:
            act = Action.objects.select_related("toolkit").get(
                toolkit__slug=toolkit, slug=action
            )
        except Action.DoesNotExist:
            return Response({"error": "unknown action"}, status=404)

        params = request.data.get("params", {}) or {}
        agent = current_agent(request)
        perm = resolve(agent, act)

        if perm == "always_deny":
            AuditLog.objects.create(
                agent=agent, toolkit=act.toolkit, action=act,
                params=params, outcome="denied",
            )
            return Response(
                {"status": "denied",
                 "message": "This action is not permitted for this agent."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if perm == "always_allow":
            result = executors.run(act, params)
            AuditLog.objects.create(
                agent=agent, toolkit=act.toolkit, action=act,
                params=params, outcome="allowed",
            )
            return Response({"status": "executed", "result": result})

        ticket = ApprovalTicket.objects.create(agent=agent, action=act, params=params)
        AuditLog.objects.create(
            agent=agent, toolkit=act.toolkit, action=act,
            params=params, outcome="pending",
        )
        return Response(
            {
                "status": "pending_approval",
                "ticket_id": str(ticket.id),
                "message": "Awaiting human approval.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ApprovalStatusView(APIView):
    def get(self, request, ticket_id):
        ticket = get_object_or_404(ApprovalTicket, id=ticket_id, agent=current_agent(request))
        if ticket.is_expired():
            ticket.status = "expired"
            ticket.save(update_fields=["status"])
            AuditLog.objects.create(
                agent=ticket.agent, toolkit=ticket.action.toolkit, action=ticket.action,
                params=ticket.params, outcome="expired",
            )
        if ticket.status == "approved":
            return Response({"status": "approved", "result": ticket.result})
        if ticket.status == "rejected":
            return Response({"status": "rejected", "reason": ticket.rejection_reason})
        return Response({"status": ticket.status})


class ApprovalResolveView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAdminUser]

    def patch(self, request, ticket_id):
        ticket = get_object_or_404(ApprovalTicket, id=ticket_id)
        if ticket.status != "pending":
            return Response({"error": f"ticket is {ticket.status}"}, status=409)
        if ticket.is_expired():
            ticket.status = "expired"
            ticket.save(update_fields=["status"])
            AuditLog.objects.create(
                agent=ticket.agent, toolkit=ticket.action.toolkit, action=ticket.action,
                params=ticket.params, outcome="expired",
            )
            return Response({"error": "ticket expired"}, status=409)

        decision = request.data.get("decision")
        if decision == "approved":
            result = executors.run(ticket.action, ticket.params)
            ticket.result = result
            ticket.status = "approved"
            ticket.save(update_fields=["result", "status"])
            AuditLog.objects.create(
                agent=ticket.agent, toolkit=ticket.action.toolkit, action=ticket.action,
                params=ticket.params, outcome="approved",
            )
            return Response({"status": "approved", "result": result})
        if decision == "rejected":
            ticket.status = "rejected"
            ticket.rejection_reason = request.data.get("reason", "")
            ticket.save(update_fields=["status", "rejection_reason"])
            AuditLog.objects.create(
                agent=ticket.agent, toolkit=ticket.action.toolkit, action=ticket.action,
                params=ticket.params, outcome="rejected",
            )
            return Response({"status": "rejected", "reason": ticket.rejection_reason})
        return Response({"error": "decision must be 'approved' or 'rejected'"}, status=400)


class AgentPermissionsView(APIView):
    def get_authenticators(self):
        if self.request and self.request.method == "PUT":
            return [AdminJWTAuthentication()]
        return super().get_authenticators()

    def get_permissions(self):
        if self.request and self.request.method == "PUT":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get(self, request, agent_id):
        if str(current_agent(request).id) != str(agent_id):
            return Response({"error": "forbidden"}, status=403)
        overrides = PermissionOverride.objects.filter(agent_id=agent_id).select_related(
            "action__toolkit"
        )
        data = serializers.PermissionOverrideSerializer(overrides, many=True).data
        return Response({"agent_id": str(agent_id), "overrides": data})

    def put(self, request, agent_id):
        action_id = request.data.get("action_id")
        permission = request.data.get("permission")
        valid = {"always_allow", "requires_approval", "always_deny"}
        if not action_id or permission not in valid:
            return Response({"error": "action_id + valid permission required"}, status=400)
        try:
            agent = Agent.objects.get(id=agent_id)
        except (Agent.DoesNotExist, ValueError):
            return Response({"error": "unknown agent"}, status=404)
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return Response({"error": "unknown action"}, status=404)

        if permission == action.default_permission:
            PermissionOverride.objects.filter(agent=agent, action=action).delete()
            return Response(
                {
                    "agent_id": str(agent.id),
                    "action": action.id,
                    "action_slug": action.slug,
                    "toolkit_slug": action.toolkit.slug,
                    "permission": permission,
                    "override": "cleared",
                }
            )

        obj, _ = PermissionOverride.objects.update_or_create(
            agent=agent, action=action, defaults={"permission": permission}
        )
        return Response(serializers.PermissionOverrideSerializer(obj).data)


class AuditListView(APIView):
    def get(self, request):
        qs = AuditLog.objects.all()
        agent_id = request.query_params.get("agent_id")
        toolkit = request.query_params.get("toolkit")
        outcome = request.query_params.get("outcome")
        if agent_id:
            qs = qs.filter(agent_uuid=agent_id)
        if toolkit:
            qs = qs.filter(toolkit_slug=toolkit)
        if outcome:
            qs = qs.filter(outcome=outcome)
        qs = qs[:500]
        return Response({"entries": serializers.AuditLogSerializer(qs, many=True).data})
