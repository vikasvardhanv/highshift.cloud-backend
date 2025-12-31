import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, BarChart3, Calendar, Palette, Sparkles, LogOut, Menu, X, Image as ImageIcon, History } from 'lucide-react';
import { useState } from 'react';

export default function Navbar() {
    const location = useLocation();
    const apiKey = localStorage.getItem('social_api_key');
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    // Always render navbar, but options depend on auth
    // if (!apiKey && location.pathname !== '/') return null; // REMOVED to show navbar always

    const handleLogout = () => {
        if (confirm('Are you sure you want to logout? This will clear your API Key.')) {
            localStorage.removeItem('social_api_key');
            window.location.href = '/';
        }
    };

    const navLinks = [
        { name: 'Connections', path: '/dashboard', icon: LayoutDashboard },
        { name: 'Analytics', path: '/analytics', icon: BarChart3 },
        { name: 'Schedule', path: '/schedule', icon: Calendar },
        { name: 'Media', path: '/media', icon: ImageIcon },
        { name: 'Ghostwriter', path: '/ai', icon: Sparkles },
        { name: 'Brand Kit', path: '/brand', icon: Palette },
        { name: 'History', path: '/history', icon: History },
    ];

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-black/80 backdrop-blur-xl">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    {/* Logo */}
                    <div className="flex-shrink-0">
                        <Link to="/" className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                                <span className="font-bold text-white">H</span>
                            </div>
                            <span className="font-bold text-xl bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">HighShift</span>
                        </Link>
                    </div>

                    {/* Desktop Navigation */}
                    <div className="hidden md:flex items-center gap-1">
                        {navLinks.map((link) => (
                            <Link
                                key={link.path}
                                to={link.path}
                                className={`px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-2 group relative overflow-hidden
                                ${location.pathname === link.path
                                        ? 'text-white bg-white/10 shadow-[inner_0_0_10px_rgba(255,255,255,0.05)]'
                                        : 'text-gray-400 hover:text-white hover:bg-white/5'
                                    }`}
                            >
                                <link.icon className={`w-4 h-4 ${location.pathname === link.path ? 'text-primary' : 'text-gray-500 group-hover:text-primary transition-colors'}`} />
                                {link.name}
                                {location.pathname === link.path && (
                                    <span className="absolute bottom-0 left-0 w-full h-[2px] bg-gradient-to-r from-primary to-secondary opacity-50"></span>
                                )}
                            </Link>
                        ))}
                    </div>

                    {/* Right Side / Mobile Menu Button */}
                    <div className="flex items-center gap-4">
                        {apiKey && (
                            <button
                                onClick={handleLogout}
                                className="hidden md:flex p-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors border border-transparent hover:border-red-500/20"
                                title="Logout"
                            >
                                <LogOut className="w-5 h-5" />
                            </button>
                        )}

                        {/* Mobile Menu Toggle */}
                        <button
                            onClick={() => setIsMenuOpen(!isMenuOpen)}
                            className="md:hidden p-2 text-gray-400 hover:text-white"
                        >
                            {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                        </button>
                    </div>
                </div>
            </div>

            {/* Mobile Menu */}
            {isMenuOpen && (
                <div className="md:hidden border-t border-white/10 bg-black/90 backdrop-blur-xl absolute w-full left-0 animate-fade-in-down">
                    <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
                        {navLinks.map((link) => (
                            <Link
                                key={link.path}
                                to={link.path}
                                onClick={() => setIsMenuOpen(false)}
                                className={`block px-3 py-3 rounded-lg text-base font-medium flex items-center gap-3
                                ${location.pathname === link.path
                                        ? 'bg-primary/20 text-white border border-primary/20'
                                        : 'text-gray-300 hover:bg-white/5 hover:text-white'
                                    }`}
                            >
                                <link.icon className={`w-5 h-5 ${location.pathname === link.path ? 'text-primary' : 'text-gray-500'}`} />
                                {link.name}
                            </Link>
                        ))}

                        {apiKey && (
                            <button
                                onClick={handleLogout}
                                className="w-full text-left flex items-center gap-3 px-3 py-3 rounded-lg text-base font-medium text-red-400 hover:bg-red-500/10"
                            >
                                <LogOut className="w-5 h-5" />
                                Logout
                            </button>
                        )}
                    </div>
                </div>
            )}
        </nav>
    );
}
