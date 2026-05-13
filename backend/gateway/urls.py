from django.urls import path

from . import views

urlpatterns = [
    path("auth/token/", views.TokenView.as_view()),
    path("auth/admin-token/", views.AdminTokenView.as_view()),
    path("external-services/toolkits/", views.ToolkitListView.as_view()),
    path("external-services/toolkits/<slug:toolkit>/actions/",views.ActionListView.as_view(),),
    path("external-services/toolkits/<slug:toolkit>/actions/<slug:action>/schema/",views.ActionSchemaView.as_view()),
    path("external-services/toolkits/<slug:toolkit>/actions/<slug:action>/call/",views.CallActionView.as_view()),
    path("external-services/approvals/<uuid:ticket_id>/status/",views.ApprovalStatusView.as_view()),
    path("external-services/approvals/<uuid:ticket_id>/resolve/",views.ApprovalResolveView.as_view()),
    path("external-services/agents/<uuid:agent_id>/permissions/",views.AgentPermissionsView.as_view()),
    path("external-services/audit/", views.AuditListView.as_view()),
]
