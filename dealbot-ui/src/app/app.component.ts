import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { ApiService, PipelineStatus, LazadaHunterStatus, LazadaGeneralStatus } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    NzLayoutModule,
    NzMenuModule,
    NzButtonModule,
    NzBadgeModule,
    NzToolTipModule
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  isCollapsed = false;
  apiOnline = false;
  dryRun = true;
  currentTime = '';

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

  lazadaGeneral: LazadaGeneralStatus = {
    is_running: false,
    started_at: 0,
    elapsed_seconds: 0,
    current_category: '',
    current_keyword: '',
    total_keywords: 0,
    current_index: 0,
    items_scanned: 0,
    deals_found: 0,
    message: '',
    last_finished_at: 0,
    last_result: null
  };

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.checkHealth();
    this.updateClock();
    setInterval(() => this.updateClock(), 1000);
    setInterval(() => this.checkHealth(), 15000);

    this.api.tasksStatus$.subscribe(st => {
      this.pipeline = st.pipeline;
      this.lazadaHunter = st.lazada_hunter;
      if (st.lazada_general) {
        this.lazadaGeneral = st.lazada_general;
      }
    });
  }

  checkHealth(): void {
    this.api.getStats().subscribe({
      next: (res) => {
        this.apiOnline = true;
        this.dryRun = res.dry_run;
      },
      error: () => {
        this.apiOnline = false;
      }
    });
  }

  updateClock(): void {
    const d = new Date();
    this.currentTime = d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
      ' • ' + d.toLocaleDateString('vi-VN');
  }
}
