import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, BotStats, PipelineStatus, LazadaHunterStatus, PipelineAutoConfig } from '../../services/api.service';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzButtonModule,
    NzTagModule,
    NzCardModule,
    NzGridModule,
    NzProgressModule,
    NzTableModule,
    NzSpinModule,
    NzAlertModule,
    NzSwitchModule,
    NzSelectModule,
    NzToolTipModule,
    RouterLink
  ],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  stats: BotStats | null = null;
  loading = false;
  actionLoading: { [key: string]: boolean } = {};

  pipelineAutoConfig: PipelineAutoConfig = {
    enabled: true,
    interval_hours: 2,
    auto_post_due: true,
    last_run_at: 0,
    next_run_at: 0
  };
  updatingAutoConfig = false;

  pipeline: PipelineStatus = {
    is_running: false,
    step: 0,
    step_name: '',
    started_at: 0,
    elapsed_seconds: 0,
    deals_added: 0,
    deals_updated: 0,
    posts_planned: 0,
    posts_done: 0,
    message: '',
    last_finished_at: 0,
    last_result: null
  };

  lazadaHunter: LazadaHunterStatus = {
    is_running: false,
    trigger_type: 'none',
    started_at: 0,
    elapsed_seconds: 0,
    total_products: 0,
    current_index: 0,
    current_product_name: '',
    deals_found: 0,
    message: '',
    last_finished_at: 0,
    last_result: null
  };

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.loadStats();
    this.loadPipelineConfig();
    this.api.tasksStatus$.subscribe(st => {
      const wasRunning = this.pipeline.is_running;
      this.pipeline = st.pipeline;
      this.lazadaHunter = st.lazada_hunter;
      if (st.pipeline) {
        if (st.pipeline.auto_enabled !== undefined) {
          this.pipelineAutoConfig.enabled = !!st.pipeline.auto_enabled;
        }
        if (st.pipeline.interval_hours !== undefined) {
          this.pipelineAutoConfig.interval_hours = st.pipeline.interval_hours;
        }
        if (st.pipeline.next_run_at !== undefined) {
          this.pipelineAutoConfig.next_run_at = st.pipeline.next_run_at;
        }
      }
      if (wasRunning && !this.pipeline.is_running) {
        this.loadStats();
        this.loadPipelineConfig();
      }
    });
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

  get hasAccountAlert(): boolean {
    if (!this.stats?.accounts) return false;
    return this.stats.accounts.some((acc: any) => acc.status === 'paused' || acc.status === 'error' || acc.status === 'cooling');
  }

  get alertAccounts(): any[] {
    if (!this.stats?.accounts) return [];
    return this.stats.accounts.filter((acc: any) => acc.status === 'paused' || acc.status === 'error' || acc.status === 'cooling');
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

  triggerRunAll(): void {
    if (this.pipeline.is_running) {
      this.msg.warning('Luồng tuần tự hiện đang chạy! Vui lòng chờ hoàn tất.');
      return;
    }
    this.actionLoading['all'] = true;
    this.api.runFullPipeline().subscribe({
      next: (res) => {
        this.actionLoading['all'] = false;
        if (res.success) {
          this.msg.success(res.message);
        } else {
          this.msg.warning(res.message);
        }
      },
      error: (err) => {
        this.actionLoading['all'] = false;
        this.msg.error(err?.error?.detail || err?.error?.message || 'Lỗi khi khởi chạy toàn bộ luồng!');
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

  loadPipelineConfig(): void {
    this.api.getPipelineConfig().subscribe({
      next: (cfg) => (this.pipelineAutoConfig = cfg),
      error: () => {}
    });
  }

  toggleAutoPipeline(enabled: boolean): void {
    this.updatingAutoConfig = true;
    this.api.updatePipelineConfig({ enabled }).subscribe({
      next: (res) => {
        this.updatingAutoConfig = false;
        this.pipelineAutoConfig.enabled = enabled;
        this.msg.success(enabled ? 'Đã bật tự động chạy Luồng Tuần Tự ngầm 24/7!' : 'Đã tạm dừng tự động chạy Luồng Tuần Tự.');
        this.loadPipelineConfig();
      },
      error: () => {
        this.updatingAutoConfig = false;
        this.msg.error('Lỗi cập nhật cấu hình tự động!');
      }
    });
  }

  changeAutoInterval(interval_hours: number): void {
    this.updatingAutoConfig = true;
    this.api.updatePipelineConfig({ interval_hours }).subscribe({
      next: (res) => {
        this.updatingAutoConfig = false;
        this.pipelineAutoConfig.interval_hours = interval_hours;
        this.msg.success(`Đã đổi chu kỳ tự động Luồng Tuần Tự sang ${interval_hours} tiếng/lần!`);
        this.loadPipelineConfig();
      },
      error: () => {
        this.updatingAutoConfig = false;
        this.msg.error('Lỗi đổi chu kỳ tự động!');
      }
    });
  }

  formatTime(ts: number | null | undefined): string {
    if (!ts) return 'Chưa có';
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' (' + d.toLocaleDateString('vi-VN') + ')';
  }
}
