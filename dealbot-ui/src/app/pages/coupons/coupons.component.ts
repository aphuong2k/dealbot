import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, CouponItem, EventItem } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzTabsModule } from 'ng-zorro-antd/tabs';

@Component({
  selector: 'app-coupons',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzInputModule,
    NzSpinModule,
    NzModalModule,
    NzTabsModule
  ],
  templateUrl: './coupons.component.html',
  styleUrls: ['./coupons.component.css']
})
export class CouponsComponent implements OnInit {
  coupons: CouponItem[] = [];
  events: EventItem[] = [];
  loading = false;
  broadcastLoading = false;

  addEventModalVisible = false;
  newEvent: EventItem = {
    title: '',
    merchant: 'shopee',
    start: '2026-10-10T00:00:00',
    end: '2026-10-11T23:59:00',
    detail: '',
    link: ''
  };

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData(): void {
    this.loading = true;
    this.api.getCoupons().subscribe({
      next: (c) => this.coupons = c
    });
    this.api.getEvents().subscribe({
      next: (e) => {
        this.events = e;
        this.loading = false;
      },
      error: () => this.loading = false
    });
  }

  triggerRefresh(): void {
    this.loading = true;
    this.api.refreshCoupons().subscribe({
      next: (res) => {
        this.msg.success(res.message);
        this.fetchData();
      },
      error: () => {
        this.loading = false;
        this.msg.error('Lỗi khi làm mới mã giảm giá!');
      }
    });
  }

  broadcastTelegram(): void {
    this.broadcastLoading = true;
    this.api.postDigestTelegram().subscribe({
      next: (res) => {
        this.broadcastLoading = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.broadcastLoading = false;
        this.msg.error('Lỗi khi phát sóng bản tin Telegram!');
      }
    });
  }

  openAddEvent(): void {
    this.newEvent = {
      title: '',
      merchant: 'shopee',
      start: new Date().toISOString().slice(0, 19),
      end: new Date(Date.now() + 86400000 * 3).toISOString().slice(0, 19),
      detail: '',
      link: ''
    };
    this.addEventModalVisible = true;
  }

  saveNewEvent(): void {
    if (!this.newEvent.title || !this.newEvent.link) {
      this.msg.warning('Vui lòng điền tiêu đề và link affiliate!');
      return;
    }
    const updated = [...this.events, this.newEvent];
    this.api.saveEvents(updated).subscribe({
      next: () => {
        this.msg.success('Đã thêm sự kiện vào events.yaml!');
        this.addEventModalVisible = false;
        this.fetchData();
      },
      error: () => this.msg.error('Lỗi khi lưu sự kiện!')
    });
  }

  deleteEvent(idx: number): void {
    const updated = this.events.filter((_, i) => i !== idx);
    this.api.saveEvents(updated).subscribe({
      next: () => {
        this.msg.success('Đã xóa sự kiện!');
        this.fetchData();
      },
      error: () => this.msg.error('Lỗi khi xóa sự kiện!')
    });
  }
}
