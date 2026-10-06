import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { ApiService } from './services/api.service';

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

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.checkHealth();
    this.updateClock();
    setInterval(() => this.updateClock(), 1000);
    setInterval(() => this.checkHealth(), 15000);
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
