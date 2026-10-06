import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, BotStats } from '../../services/api.service';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    NzButtonModule,
    NzTagModule,
    NzCardModule,
    NzGridModule,
    NzProgressModule,
    NzTableModule,
    NzSpinModule,
    NzAlertModule,
    RouterLink
  ],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  stats: BotStats | null = null;
  loading = false;
  actionLoading: { [key: string]: boolean } = {};

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.loadStats();
  }

  loadStats(): void {
    this.loading = true;
    this.api.getStats().subscribe({
      next: (res) => {
        this.stats = res;
        this.loading = false;
      },
      error: (err) => {
        console.error(err);
        this.loading = false;
        this.msg.error('Không thể kết nối đến Backend API (Port 8000). Vui lòng chạy api.py!');
      }
    });
  }

  triggerPlan(): void {
    this.actionLoading['plan'] = true;
    this.api.planPosts().subscribe({
      next: (res) => {
        this.actionLoading['plan'] = false;
        this.msg.success(res.message);
        this.loadStats();
      },
      error: () => {
        this.actionLoading['plan'] = false;
        this.msg.error('Lỗi khi lập lịch bài đăng!');
      }
    });
  }

  triggerPost(): void {
    this.actionLoading['post'] = true;
    this.api.runDuePosts().subscribe({
      next: (res) => {
        this.actionLoading['post'] = false;
        this.msg.success(res.message);
        this.loadStats();
      },
      error: () => {
        this.actionLoading['post'] = false;
        this.msg.error('Lỗi khi kích hoạt phiên đăng bài!');
      }
    });
  }

  triggerCrawl(): void {
    this.actionLoading['crawl'] = true;
    this.api.crawlDeals().subscribe({
      next: (res) => {
        this.actionLoading['crawl'] = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.actionLoading['crawl'] = false;
        this.msg.error('Lỗi khi kích hoạt cào deal!');
      }
    });
  }

  triggerWarmup(): void {
    this.actionLoading['warmup'] = true;
    this.api.warmupAccounts().subscribe({
      next: (res) => {
        this.actionLoading['warmup'] = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.actionLoading['warmup'] = false;
        this.msg.error('Lỗi khi kích hoạt nuôi nick!');
      }
    });
  }

  triggerTelegramDigest(): void {
    this.actionLoading['tg'] = true;
    this.api.postDigestTelegram().subscribe({
      next: (res) => {
        this.actionLoading['tg'] = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.actionLoading['tg'] = false;
        this.msg.error('Lỗi khi đăng lên Telegram Channel!');
      }
    });
  }
}
