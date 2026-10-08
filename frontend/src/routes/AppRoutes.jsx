import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "../layouts/AppShell";
import { useAuth } from "../hooks/useAuth";
import AdminDashboardPage from "../pages/admin/DashboardPage";
import AdminProfilePage from "../pages/admin/ProfilePage";
import RolesPermissionsPage from "../pages/admin/RolesPermissionsPage";
import SystemReportsPage from "../pages/admin/SystemReportsPage";
import UserDetailsPage from "../pages/admin/UserDetailsPage";
import UsersPage from "../pages/admin/UsersPage";
import ComingSoonPage from "../pages/ComingSoonPage";
import ClaimDetailsPage from "../pages/customer/ClaimDetailsPage";
import ClaimTimelinePage from "../pages/customer/ClaimTimelinePage";
import ClaimsListPage from "../pages/customer/ClaimsListPage";
import CustomerDashboardPage from "../pages/customer/DashboardPage";
import DocumentsPage from "../pages/customer/DocumentsPage";
import NewClaimPage from "../pages/customer/NewClaimPage";
import NotificationsPage from "../pages/customer/NotificationsPage";
import PoliciesPage from "../pages/customer/PoliciesPage";
import ProfilePage from "../pages/customer/ProfilePage";
import SupportPage from "../pages/customer/SupportPage";
import SupportRequestPage from "../pages/customer/SupportRequestPage";
import UploadDocumentsPage from "../pages/customer/UploadDocumentsPage";
import LoginPage from "../pages/LoginPage";
import NotFoundPage from "../pages/NotFoundPage";
import AiInsightsPage from "../pages/officer/AiInsightsPage";
import AllClaimsPage from "../pages/officer/AllClaimsPage";
import AuditLogsPage from "../pages/officer/AuditLogsPage";
import ClaimSearchPage from "../pages/officer/ClaimSearchPage";
import OfficerClaimDetailsPage from "../pages/officer/ClaimDetailsPage";
import OfficerDashboardPage from "../pages/officer/DashboardPage";
import DecisionPage from "../pages/officer/DecisionPage";
import DocumentConsistencyPage from "../pages/officer/DocumentConsistencyPage";
import EscalationsPage from "../pages/officer/EscalationsPage";
import EvidenceCheckPage from "../pages/officer/EvidenceCheckPage";
import EstimateAnalysisPage from "../pages/officer/EstimateAnalysisPage";
import FraudRiskPage from "../pages/officer/FraudRiskPage";
import OfficerNotificationsPage from "../pages/officer/NotificationsPage";
import PerformanceReportsPage from "../pages/officer/PerformanceReportsPage";
import OfficerProfilePage from "../pages/officer/ProfilePage";
import RfiPage from "../pages/officer/RfiPage";
import SlaReportsPage from "../pages/officer/SlaReportsPage";
import OfficerSupportPage from "../pages/officer/SupportPage";
import WorkQueuePage from "../pages/officer/WorkQueuePage";
import SurveyorClaimDetailsPage from "../pages/surveyor/ClaimDetailsPage";
import SurveyorClaimsListPage from "../pages/surveyor/ClaimsListPage";
import SurveyorDashboardPage from "../pages/surveyor/DashboardPage";
import EvidencePage from "../pages/surveyor/EvidencePage";
import InspectionHistoryPage from "../pages/surveyor/InspectionHistoryPage";
import InspectionWorkspacePage from "../pages/surveyor/InspectionWorkspacePage";
import SurveyorNotificationsPage from "../pages/surveyor/NotificationsPage";
import SurveyorProfilePage from "../pages/surveyor/ProfilePage";
import RepairEstimatePage from "../pages/surveyor/RepairEstimatePage";
import SurveyReportPage from "../pages/surveyor/SurveyReportPage";
import SurveyorSupportPage from "../pages/surveyor/SupportPage";
import VehicleDamagePage from "../pages/surveyor/VehicleDamagePage";
import LoadingState from "../components/common/LoadingState";
import { getRoleHomePath } from "../utils/roles";
import ProtectedRoute from "./ProtectedRoute";
import PublicRoute from "./PublicRoute";
import RoleProtectedRoute from "./RoleProtectedRoute";

function RootRedirect() {
  const { isAuthenticated, isLoading, role } = useAuth();

  if (isLoading) {
    return <LoadingState label="Loading CI-MICOP..." />;
  }

  return <Navigate to={isAuthenticated ? getRoleHomePath(role) : "/login"} replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />

      <Route element={<PublicRoute />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<RoleProtectedRoute allowedRoles={["Customer"]} />}>
          <Route path="/customer" element={<AppShell />}>
            <Route index element={<CustomerDashboardPage />} />
            <Route path="claims" element={<ClaimsListPage />} />
            <Route path="claims/new" element={<NewClaimPage />} />
            <Route path="claims/:claimId" element={<ClaimDetailsPage />} />
            <Route path="claims/:claimId/timeline" element={<ClaimTimelinePage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="documents/upload" element={<UploadDocumentsPage />} />
            <Route path="policies" element={<PoliciesPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="support" element={<SupportPage />} />
            <Route path="support/request" element={<SupportRequestPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="*" element={<ComingSoonPage />} />
          </Route>
        </Route>

        <Route element={<RoleProtectedRoute allowedRoles={["Surveyor"]} />}>
          <Route path="/surveyor" element={<AppShell />}>
            <Route index element={<SurveyorDashboardPage />} />
            <Route path="claims" element={<SurveyorClaimsListPage />} />
            <Route path="claims/:claimId" element={<SurveyorClaimDetailsPage />} />
            <Route path="claims/:claimId/inspection" element={<InspectionWorkspacePage />} />
            <Route path="claims/:claimId/damage" element={<VehicleDamagePage />} />
            <Route path="claims/:claimId/evidence" element={<EvidencePage />} />
            <Route path="claims/:claimId/repair-estimate" element={<RepairEstimatePage />} />
            <Route path="claims/:claimId/report" element={<SurveyReportPage />} />
            <Route path="history" element={<InspectionHistoryPage />} />
            <Route path="notifications" element={<SurveyorNotificationsPage />} />
            <Route path="profile" element={<SurveyorProfilePage />} />
            <Route path="support" element={<SurveyorSupportPage />} />
            <Route path="*" element={<ComingSoonPage />} />
          </Route>
        </Route>

        <Route element={<RoleProtectedRoute allowedRoles={["Claims Officer"]} />}>
          <Route path="/officer" element={<AppShell />}>
            <Route index element={<OfficerDashboardPage />} />
            <Route path="queue" element={<WorkQueuePage />} />
            <Route path="claims" element={<AllClaimsPage />} />
            <Route path="search" element={<ClaimSearchPage />} />
            <Route path="claims/:claimId" element={<OfficerClaimDetailsPage />} />
            <Route path="claims/:claimId/fraud-risk" element={<FraudRiskPage />} />
            <Route path="claims/:claimId/ai-insights" element={<AiInsightsPage />} />
            <Route path="claims/:claimId/consistency" element={<DocumentConsistencyPage />} />
            <Route path="claims/:claimId/evidence" element={<EvidenceCheckPage />} />
            <Route path="claims/:claimId/estimate" element={<EstimateAnalysisPage />} />
            <Route path="claims/:claimId/decision" element={<DecisionPage />} />
            <Route path="escalations" element={<EscalationsPage />} />
            <Route path="rfi" element={<RfiPage />} />
            <Route path="performance-reports" element={<PerformanceReportsPage />} />
            <Route path="sla-reports" element={<SlaReportsPage />} />
            <Route path="audit-logs" element={<AuditLogsPage />} />
            <Route path="notifications" element={<OfficerNotificationsPage />} />
            <Route path="profile" element={<OfficerProfilePage />} />
            <Route path="support" element={<OfficerSupportPage />} />
            <Route path="*" element={<ComingSoonPage />} />
          </Route>
        </Route>

        <Route element={<RoleProtectedRoute allowedRoles={["Admin"]} />}>
          <Route path="/admin" element={<AppShell />}>
            <Route index element={<AdminDashboardPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="users/:userId" element={<UserDetailsPage />} />
            <Route path="roles-permissions" element={<RolesPermissionsPage />} />
            <Route path="system-reports" element={<SystemReportsPage />} />
            {/* The officer audit page only uses endpoints Admin may also call. */}
            <Route path="audit-logs" element={<AuditLogsPage />} />
            <Route path="profile" element={<AdminProfilePage />} />
            <Route path="*" element={<ComingSoonPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
