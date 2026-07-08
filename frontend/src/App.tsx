import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import SignUp from "./pages/SignUp";
import Check from "./pages/Check";
import Select from "./pages/Select";
import Connect from "./pages/Connect";
import Upload from "./pages/Upload";
import Processing from "./pages/Processing";
import Result from "./pages/Result";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import InviteAccept from "./pages/InviteAccept";
import Schedule from "./pages/Schedule";
import Notification from "./pages/Notification";
import Records from "./pages/Records";
import PrescriptionDetail from "./pages/PrescriptionDetail";
import PrescriptionReview from "./pages/PrescriptionReview";
import MyPage from "./pages/MyPage";
import PatientManagement from "./pages/PatientManagement";
import MonitoringDashboard from "./pages/MonitoringDashboard";
import DrugDetail from "./pages/DrugDetail";
import NotFound from "./pages/NotFound";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<SignUp />} />
        <Route path="/check" element={<Check />} />
        <Route path="/select" element={<Select />} />
        <Route path="/connect" element={<Connect />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/processing" element={<Processing />} />
        <Route path="/result" element={<Result />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/invite/:token" element={<InviteAccept />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/notification" element={<Notification />} />
        <Route path="/records" element={<Records />} />
        <Route path="/records/:recordId" element={<PrescriptionDetail />} />
        <Route path="/records/:recordId/review" element={<PrescriptionReview />} />
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/patients" element={<PatientManagement />} />
        <Route path="/monitoring" element={<MonitoringDashboard />} />
        <Route path="/drugs/:scheduleId" element={<DrugDetail />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
