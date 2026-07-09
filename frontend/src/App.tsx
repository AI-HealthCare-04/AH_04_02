import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import Footer from "./components/Footer";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import SignUp from "./pages/SignUp";
import Check from "./pages/Check";
import Select from "./pages/Select";
import Connect from "./pages/Connect";
import Upload from "./pages/Upload";
import Processing from "./pages/Processing";
import OcrError from "./pages/OcrError";
import Result from "./pages/Result";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import InviteAccept from "./pages/InviteAccept";
import Schedule from "./pages/Schedule";
import Notification from "./pages/Notification";
import Records from "./pages/Records";
import PrescriptionDetail from "./pages/PrescriptionDetail";
import PrescriptionReview from "./pages/PrescriptionReview";
import MedGuide from "./pages/MedGuide";
import MyPage from "./pages/MyPage";
import PatientManagement from "./pages/PatientManagement";
import CareEducation from "./pages/CareEducation";
import MonitoringDashboard from "./pages/MonitoringDashboard";
import MonitoringDayLogs from "./pages/MonitoringDayLogs";
import DrugDetail from "./pages/DrugDetail";
import DrugInfo from "./pages/DrugInfo";
import NotFound from "./pages/NotFound";

function Layout() {
  return (
    <>
      <Outlet />
      <Footer />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<SignUp />} />
          <Route path="/check" element={<Check />} />
          <Route path="/select" element={<Select />} />
          <Route path="/connect" element={<Connect />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/processing" element={<Processing />} />
          <Route path="/ocr-error" element={<OcrError />} />
          <Route path="/result" element={<Result />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/invite/:token" element={<InviteAccept />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/notification" element={<Notification />} />
          <Route path="/records" element={<Records />} />
          <Route path="/records/:recordId" element={<PrescriptionDetail />} />
          <Route path="/records/:recordId/review" element={<PrescriptionReview />} />
          <Route path="/records/:recordId/guide" element={<MedGuide />} />
          <Route path="/records/:recordId/drugs/:medId" element={<DrugInfo />} />
          <Route path="/mypage" element={<MyPage />} />
          <Route path="/patients" element={<PatientManagement />} />
          <Route path="/care-education" element={<CareEducation />} />
          <Route path="/monitoring" element={<MonitoringDashboard />} />
          <Route path="/monitoring/logs/:date" element={<MonitoringDayLogs />} />
          <Route path="/drugs/:scheduleId" element={<DrugDetail />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
