import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, GroupItem, ScannedGroup } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzPopconfirmModule } from 'ng-zorro-antd/popconfirm';

@Component({
  selector: 'app-groups',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzInputModule,
    NzSelectModule,
    NzTagModule,
    NzSwitchModule,
    NzProgressModule,
    NzSpinModule,
    NzTabsModule,
    NzModalModule,
    NzEmptyModule,
    NzBadgeModule,
    NzPopconfirmModule
  ],
  templateUrl: './groups.component.html',
  styleUrls: ['./groups.component.css']
})
export class GroupsComponent implements OnInit {
  groups: GroupItem[] = [];
  loading = false;
  discoverLoading = false;

  selectedTab = 'all';
  searchQuery = '';
  selectedKind = '';
  selectedAccountFilter = 'all';

  accountOptions = [
    { label: 'Chưa gán', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  // Group Scanner
  scanModalVisible = false;
  scanLoading = false;
  scanAccount = '';
  scannedGroups: ScannedGroup[] = [];
  scannedMessage = '';
  scannedSearchQuery = '';

  // Leave group
  leavingGroupUrl = '';

  constructor(
    private api: ApiService,
    private msg: NzMessageService,
    private modal: NzModalService
  ) {}

  ngOnInit(): void {
    this.fetchGroups();
  }

  fetchGroups(): void {
    this.loading = true;
    const statusParam = this.selectedTab === 'all' ? undefined : this.selectedTab;
    const accountParam = this.selectedAccountFilter === 'all' ? undefined : this.selectedAccountFilter;
    this.api.getGroups(statusParam, this.selectedKind || undefined, this.searchQuery || undefined, accountParam).subscribe({
      next: (data) => {
        this.groups = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.msg.error('Không thể tải danh sách nhóm!');
      }
    });
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedAccountFilter = 'all';
    this.fetchGroups();
  }

  onTabChange(index: number): void {
    const tabs = ['all', 'candidate', 'joined', 'cooling_down', 'banned'];
    this.selectedTab = tabs[index] || 'all';
    this.fetchGroups();
  }

  get filteredScannedGroups(): ScannedGroup[] {
    if (!this.scannedSearchQuery.trim()) return this.scannedGroups;
    const q = this.scannedSearchQuery.toLowerCase();
    return this.scannedGroups.filter(g => (g.name || '').toLowerCase().includes(q) || (g.url || '').toLowerCase().includes(q));
  }

  updateStatus(g: GroupItem, newStatus: any): void {
    this.api.updateGroup(g.url, { status: newStatus }).subscribe({
      next: () => {
        g.status = newStatus;
        if (newStatus === 'joined') g.consecutive_fails = 0;
        this.msg.success(`Đã cập nhật trạng thái nhóm sang "${newStatus}"!`);
      },
      error: () => this.msg.error('Lỗi khi cập nhật trạng thái nhóm!')
    });
  }

  onAllowLinkChange(g: GroupItem, checked: boolean): void {
    const val = checked ? 1 : 0;
    this.api.updateGroup(g.url, { allow_link: val }).subscribe({
      next: () => {
        g.allow_link = val;
        this.msg.success(`Đã ${checked ? 'cho phép' : 'chặn'} link comment nhóm!`);
      },
      error: () => this.msg.error('Lỗi cập nhật cài đặt link!')
    });
  }

  onAccountChange(g: GroupItem, acc: string): void {
    this.api.updateGroup(g.url, { account: acc }).subscribe({
      next: () => {
        g.account = acc;
        this.msg.success(`Đã gán cố định nhóm cho ${acc}!`);
      },
      error: () => this.msg.error('Lỗi khi gán nick!')
    });
  }

  triggerDiscover(): void {
    this.discoverLoading = true;
    this.api.discoverGroups().subscribe({
      next: (res) => {
        this.discoverLoading = false;
        this.msg.success(res.message);
        setTimeout(() => this.fetchGroups(), 3000);
      },
      error: () => {
        this.discoverLoading = false;
        this.msg.error('Lỗi khi quét nhóm mới!');
      }
    });
  }

  // --- SCAN JOINED GROUPS ---
  openScanModal(): void {
    this.scanModalVisible = true;
    this.scannedGroups = [];
    this.scannedMessage = '';
    this.scanAccount = this.accountOptions.length > 1 ? this.accountOptions[1].value : '';
  }

  closeScanModal(): void {
    this.scanModalVisible = false;
  }

  startScan(): void {
    if (!this.scanAccount) {
      this.msg.warning('Vui lòng chọn tài khoản để quét!');
      return;
    }
    this.scanLoading = true;
    this.scannedGroups = [];
    this.scannedMessage = '';
    this.api.scanJoinedGroups(this.scanAccount).subscribe({
      next: (res) => {
        this.scanLoading = false;
        this.scannedGroups = res.groups || [];
        this.scannedMessage = res.message;
        if (res.success) {
          this.msg.success(res.message);
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.scanLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi quét danh sách group!');
      }
    });
  }

  // --- LEAVE GROUP ---
  confirmLeaveGroup(g: GroupItem): void {
    if (!g.account) {
      this.msg.warning('Nhóm chưa được gán nick! Hãy chọn nick trước khi rời nhóm.');
      return;
    }
    this.leavingGroupUrl = g.url;
    this.api.leaveGroup(g.account, g.url).subscribe({
      next: (res) => {
        this.leavingGroupUrl = '';
        if (res.success) {
          this.msg.success(res.message);
          g.status = 'skip' as any;
          // Refresh danh sách
          setTimeout(() => this.fetchGroups(), 1000);
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.leavingGroupUrl = '';
        this.msg.error(err?.error?.detail || 'Lỗi khi rời nhóm!');
      }
    });
  }

  leaveScannedGroup(sg: ScannedGroup): void {
    if (!this.scanAccount) {
      this.msg.warning('Không xác định được nick!');
      return;
    }
    this.leavingGroupUrl = sg.url;
    this.api.leaveGroup(this.scanAccount, sg.url).subscribe({
      next: (res) => {
        this.leavingGroupUrl = '';
        if (res.success) {
          this.msg.success(res.message);
          // Xóa khỏi danh sách hiển thị
          this.scannedGroups = this.scannedGroups.filter(g => g.url !== sg.url);
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.leavingGroupUrl = '';
        this.msg.error(err?.error?.detail || 'Lỗi khi rời nhóm!');
      }
    });
  }

  // --- REMOVE GROUP FROM DB ---
  removeGroupFromDb(g: GroupItem): void {
    this.api.removeGroupFromDb(g.url).subscribe({
      next: (res) => {
        this.msg.success(res.message);
        this.groups = this.groups.filter(item => item.url !== g.url);
      },
      error: (err) => {
        this.msg.error(err?.error?.detail || 'Lỗi khi xóa group!');
      }
    });
  }

  // --- IMPORT SCANNED GROUPS TO DB ---
  importLoading = false;

  importGroup(sg: ScannedGroup): void {
    const payload = [{
      url: sg.url,
      name: sg.name,
      account: this.scanAccount || '',
      status: 'joined',
      kind: 'dealhunt',
      niche: 'săn sale'
    }];
    this.api.importScannedGroups(payload).subscribe({
      next: (res) => {
        this.msg.success(`Đã thêm "${sg.name || sg.url}" vào bot!`);
        this.fetchGroups();
      },
      error: (err) => {
        this.msg.error(err?.error?.detail || 'Lỗi khi thêm nhóm vào bot!');
      }
    });
  }

  importAllScanned(): void {
    if (this.scannedGroups.length === 0) return;
    this.importLoading = true;
    const payload = this.scannedGroups.map(sg => ({
      url: sg.url,
      name: sg.name,
      account: this.scanAccount || '',
      status: 'joined',
      kind: 'dealhunt',
      niche: 'săn sale'
    }));
    this.api.importScannedGroups(payload).subscribe({
      next: (res) => {
        this.importLoading = false;
        this.msg.success(res.message);
        this.fetchGroups();
      },
      error: (err) => {
        this.importLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi nhập danh sách nhóm!');
      }
    });
  }

  isGroupInDb(sg: ScannedGroup): boolean {
    return this.groups.some(g => g.url === sg.url);
  }
}

