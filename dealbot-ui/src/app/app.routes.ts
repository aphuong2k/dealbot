import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { DealsComponent } from './pages/deals/deals.component';
import { LazadaDealsComponent } from './pages/lazada-deals/lazada-deals.component';
import { GroupsComponent } from './pages/groups/groups.component';
import { PostsComponent } from './pages/posts/posts.component';
import { CouponsComponent } from './pages/coupons/coupons.component';
import { SettingsComponent } from './pages/settings/settings.component';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: DashboardComponent, title: 'Tổng Quan | Dealbot Studio' },
  { path: 'deals', component: DealsComponent, title: 'Kho Deal | Dealbot Studio' },
  { path: 'lazada-deals', component: LazadaDealsComponent, title: 'Săn Deal LazMall | Dealbot Studio' },
  { path: 'groups', component: GroupsComponent, title: 'Hội Nhóm & Đăng Bài | Dealbot Studio' },
  { path: 'posts', redirectTo: 'groups', pathMatch: 'full' },
  { path: 'coupons', component: CouponsComponent, title: 'Voucher & Sự Kiện | Dealbot Studio' },
  { path: 'settings', component: SettingsComponent, title: 'Cấu Hình & Nick | Dealbot Studio' },
  { path: '**', redirectTo: 'dashboard' }
];
