import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { getAccounts, getAnalytics } from '../services/api';
import { BarChart3, TrendingUp, Users, Activity, ArrowUp, ArrowDown, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Analytics() {
    const [accounts, setAccounts] = useState([]);
    const [selectedAccount, setSelectedAccount] = useState(null);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(false);
    const apiKey = localStorage.getItem('social_api_key');

    useEffect(() => {
        if (apiKey) loadAccounts();
    }, [apiKey]);

    if (!apiKey) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 animate-fade-in">
                <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6 border border-primary/20">
                    <BarChart3 className="w-10 h-10 text-primary" />
                </div>
                <h2 className="text-3xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Unlock Analytics</h2>
                <p className="text-gray-400 mb-8 max-w-md mx-auto">Connect your social accounts to view detailed performance metrics, audience growth, and engagement reports.</p>
                <Link to="/dashboard" className="px-8 py-3 rounded-full bg-primary hover:bg-primaryHover text-white font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105">
                    Connect Accounts
                </Link>
            </div>
        );
    }

    useEffect(() => {
        if (selectedAccount) {
            loadStats(selectedAccount);
        }
    }, [selectedAccount]);

    const loadAccounts = async () => {
        try {
            const data = await getAccounts();
            setAccounts(data.accounts || []);
            if (data.accounts?.length > 0) {
                setSelectedAccount(data.accounts[0].accountId);
            }
        } catch (err) {
            console.error('Failed to load accounts', err);
        }
    };

    const loadStats = async (accountId) => {
        setLoading(true);
        try {
            const data = await getAnalytics(accountId);
            setStats(data);
        } catch (err) {
            console.error('Failed to load analytics', err);
        } finally {
            setLoading(false);
        }
    };

    const StatCard = ({ title, value, subtext, icon: Icon, delay }) => (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay }}
            className="glass-card p-6 rounded-2xl relative overflow-hidden group hover:border-primary/30 transition-all"
        >
            <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                <Icon className="w-24 h-24 rotate-12" />
            </div>
            <div className="relative z-10">
                <div className="flex items-center gap-2 mb-2 text-gray-400">
                    <Icon className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">{title}</span>
                </div>
                <div className="text-3xl font-bold text-white mb-1">{value?.toLocaleString()}</div>
                <div className={`text-xs font-medium flex items-center gap-1 ${subtext.startsWith('+') ? 'text-green-400' : 'text-gray-500'}`}>
                    {subtext.startsWith('+') && <TrendingUp className="w-3 h-3" />}
                    {subtext}
                </div>
            </div>
        </motion.div>
    );

    return (
        <div className="max-w-6xl mx-auto pb-20">
            <div className="mb-10 flex flex-col md:flex-row items-start md:items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Analytics Dashboard</h1>
                    <p className="text-gray-400 mt-2">Track your growth across all connected channels.</p>
                </div>

                <div className="w-full md:w-auto">
                    <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Select Account</label>
                    <select
                        className="w-full md:w-64 bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-primary/50 transition-all"
                        value={selectedAccount || ''}
                        onChange={(e) => setSelectedAccount(e.target.value)}
                    >
                        {accounts.map(acc => (
                            <option key={acc.accountId} value={acc.accountId} className="bg-gray-900">
                                {acc.platform.charAt(0).toUpperCase() + acc.platform.slice(1)} - {acc.displayName}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center py-20">
                    <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                </div>
            ) : !stats ? (
                <div className="text-center py-20 text-gray-500">
                    Select an account to view analytics.
                </div>
            ) : (
                <>
                    {/* Key Metrics Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                        <StatCard
                            title="Total Impressions"
                            value={stats.summary.totalImpressions}
                            subtext="Last 30 Days"
                            icon={Activity}
                            delay={0.1}
                        />
                        <StatCard
                            title="Engagement"
                            value={stats.summary.totalEngagement}
                            subtext={`${((stats.summary.totalEngagement / stats.summary.totalImpressions) * 100).toFixed(1)}% Rate`}
                            icon={BarChart3}
                            delay={0.2}
                        />
                        <StatCard
                            title="Follower Growth"
                            value={stats.summary.currentFollowers}
                            subtext={`${stats.summary.followerGrowth > 0 ? '+' : ''}${stats.summary.followerGrowth} vs last month`}
                            icon={Users}
                            delay={0.3}
                        />
                    </div>

                    {/* Simple Growth Chart (CSS Bars) */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="glass-card p-8 rounded-2xl"
                    >
                        <h3 className="text-xl font-bold mb-6">Growth Trend (30 Days)</h3>
                        <div className="h-64 flex items-end gap-2">
                            {stats.daily.map((day, i) => {
                                // Normalize height based on max value to fit container
                                const maxVal = Math.max(...stats.daily.map(d => d.metrics.impressions));
                                const height = (day.metrics.impressions / maxVal) * 100;

                                return (
                                    <div key={i} className="flex-1 flex flex-col justify-end group cursor-pointer relative">
                                        {/* Tooltip */}
                                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-black/80 px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                                            {day.metrics.impressions} Views<br />{new Date(day.date).toLocaleDateString()}
                                        </div>
                                        <div
                                            className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t-sm"
                                            style={{ height: `${height}%` }}
                                        ></div>
                                    </div>
                                )
                            })}
                        </div>
                        <div className="flex justify-between mt-4 text-xs text-gray-500 uppercase font-semibold">
                            <span>30 Days Ago</span>
                            <span>Today</span>
                        </div>
                    </motion.div>
                </>
            )}
        </div>
    );
}
