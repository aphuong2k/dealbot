import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzCardModule } from 'ng-zorro-antd/card';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzButtonModule,
    NzInputModule,
    NzSwitchModule,
    NzSpinModule,
    NzCardModule
  ],
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.css']
})
export class SettingsComponent implements OnInit {
  config: any = null;
  loading = false;
  saveLoading = false;
  testTelegramLoading = false;
  warmupLoading = false;

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchConfig();
  }

  fetchConfig(): void {
    this.loading = true;
    this.api.getConfig().subscribe({
      next: (cfg) => {
        this.config = cfg;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.msg.error('Không thể tải cấu hình config.yaml!');
      }
    });
  }

  saveConfig(): void {
    this.saveLoading = true;
    this.api.updateConfig(this.config).subscribe({
      next: (res) => {
        this.saveLoading = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.saveLoading = false;
        this.msg.error('Lỗi khi lưu cấu hình!');
      }
    });
  }

  testTelegram(): void {
    this.testTelegramLoading = true;
    this.api.testTelegramNotify().subscribe({
      next: (res) => {
        this.testTelegramLoading = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.testTelegramLoading = false;
        this.msg.error('Lỗi gửi tin nhắn test Telegram!');
      }
    });
  }

  triggerWarmup(): void {
    this.warmupLoading = true;
    this.api.warmupAccounts().subscribe({
      next: (res) => {
        this.warmupLoading = false;
        this.msg.success(res.message);
      },
      error: () => {
        this.warmupLoading = false;
        this.msg.error('Lỗi khi kích hoạt phiên nuôi nick!');
      }
    });
  }
}
