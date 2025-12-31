import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Analytics from './pages/Analytics';
import Schedule from './pages/Schedule';
import BrandKit from './pages/BrandKit';
import Ghostwriter from './pages/Ghostwriter';
import MediaLibrary from './pages/MediaLibrary';
import History from './pages/History';
import AuthCallback from './pages/AuthCallback';
import Navbar from './components/Navbar';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-background text-white selection:bg-primary/30 font-sans">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/brand" element={<BrandKit />} />
            <Route path="/ai" element={<Ghostwriter />} />
            <Route path="/media" element={<MediaLibrary />} />
            <Route path="/history" element={<History />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
