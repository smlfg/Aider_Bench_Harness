import React from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, TrendingUp, List, Rocket } from 'lucide-react';

const Layout: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Analysis', icon: LayoutDashboard },
    { path: '/trajectory', label: 'Trajectory', icon: TrendingUp },
    { path: '/runs', label: 'Runs', icon: List },
    { path: '/launch', label: 'Launch', icon: Rocket },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
              <span className="text-white font-bold">H</span>
            </div>
            <h1 className="text-xl font-bold text-gray-900">Harness Cockpit</h1>
          </div>
          <nav className="flex space-x-6">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
