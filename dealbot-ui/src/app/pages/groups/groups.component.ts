import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, GroupItem } from '../../services/api.service';
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
    NzTabsModule
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

  accountOptions = [
    { label: 'Chưa gán', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchGroups();
  }

  fetchGroups(): void {
    this.loading = true;
    const statusParam = this.selectedTab === 'all' ? undefined : this.selectedTab;
    this.api.getGroups(statusParam, this.selectedKind || undefined, this.searchQuery || undefined).subscribe({
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

  onTabChange(index: number): void {
    const tabs = ['all', 'candidate', 'joined', 'cooling_down', 'banned'];
    this.selectedTab = tabs[index] || 'all';
    this.fetchGroups();
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
}
