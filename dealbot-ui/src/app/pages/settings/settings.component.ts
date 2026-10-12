import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, AccountCookieInfo, ShopeeCookieInfo, ShopeeCategory } from '../../services/api.service';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';

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
    NzCardModule,
    NzModalModule,
    NzTagModule,
    NzCheckboxModule
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

  // Quản lý Cookie Facebook
  cookiesInfo: { [accountName: string]: AccountCookieInfo } = {};
  testingAccount: { [accountName: string]: boolean } = {};
  cookieModalVisible = false;
  selectedAccount = '';
  cookieInput = '';
  cookieLoading = false;
  cookieSaving = false;
  currentCookieInfo: AccountCookieInfo | null = null;

  // Quản lý Cookie Shopee Affiliate
  shopeeCookieInfo: ShopeeCookieInfo | null = null;
  testingShopee = false;
  shopeeModalVisible = false;
  shopeeCookieInput = '';
  shopeeCookieSaving = false;
  shopeeCookieLoading = false;

  // Quản lý Cây Danh Mục Ngành Hàng Shopee
  categoriesModalVisible = false;
  categoriesLoading = false;
  shopeeCategories: ShopeeCategory[] = [];
  selectedCategories: { [name: string]: boolean } = {};
  syncingCategories = false;

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchConfig();
    this.fetchCookiesStatus();
    this.fetchShopeeCookieStatus();
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

  fetchCookiesStatus(): void {
    this.api.getAccountsCookies().subscribe({
      next: (list) => {
        const map: { [key: string]: AccountCookieInfo } = {};
        for (const item of list) {
          map[item.account] = item;
        }
        this.cookiesInfo = map;
      },
      error: () => {}
    });
  }

  openCookieModal(accountName: string): void {
    this.selectedAccount = accountName;
    this.cookieModalVisible = true;
    this.cookieLoading = true;
    this.cookieInput = '';
    this.currentCookieInfo = null;

    this.api.getAccountCookie(accountName).subscribe({
      next: (info) => {
        this.currentCookieInfo = info;
        this.cookieInput = info.raw_content || '';
        this.cookieLoading = false;
      },
      error: () => {
        this.cookieLoading = false;
        this.msg.error('Lỗi khi đọc file cookie!');
      }
    });
  }

  closeCookieModal(): void {
    this.cookieModalVisible = false;
    this.cookieInput = '';
    this.selectedAccount = '';
    this.currentCookieInfo = null;
  }

  saveCookie(): void {
    if (!this.cookieInput.trim()) {
      this.msg.warning('Vui lòng nhập hoặc dán nội dung Cookie!');
      return;
    }

    this.cookieSaving = true;
    this.api.saveAccountCookie(this.selectedAccount, this.cookieInput).subscribe({
      next: (res) => {
        this.cookieSaving = false;
        this.msg.success(res.message);
        if (res.info) {
          this.cookiesInfo[this.selectedAccount] = res.info;
          this.currentCookieInfo = res.info;
        }
        this.cookieModalVisible = false;
        this.fetchCookiesStatus();
      },
      error: (err) => {
        this.cookieSaving = false;
        const errMsg = err?.error?.detail || 'Lỗi khi lưu cookie! Hãy kiểm tra định dạng.';
        this.msg.error(errMsg);
      }
    });
  }

  deleteCookie(): void {
    if (!confirm(`Bạn có chắc muốn xóa file cookie của nick "${this.selectedAccount}"?`)) {
      return;
    }
    this.api.deleteAccountCookie(this.selectedAccount).subscribe({
      next: (res) => {
        this.msg.info(res.message);
        this.cookieInput = '';
        this.fetchCookiesStatus();
        this.closeCookieModal();
      },
      error: () => {
        this.msg.error('Lỗi khi xóa file cookie!');
      }
    });
  }

  onFileUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        this.cookieInput = text;
        this.msg.success(`Đã tải nội dung file "${file.name}"!`);
      };
      reader.readAsText(file);
    }
  }

  formatJson(): void {
    try {
      const obj = JSON.parse(this.cookieInput);
      this.cookieInput = JSON.stringify(obj, null, 2);
      this.msg.success('Đã căn chỉnh định dạng JSON!');
    } catch {
      this.msg.warning('Nội dung không phải là cú pháp JSON hợp lệ.');
    }
  }

  testConnect(accountName: string): void {
    this.testingAccount[accountName] = true;
    this.api.testFacebookConnect(accountName).subscribe({
      next: (res) => {
        this.testingAccount[accountName] = false;
        if (res.success) {
          this.msg.success(res.message, { nzDuration: 6000 });
        } else {
          this.msg.warning(res.message, { nzDuration: 8000 });
        }
      },
      error: (err) => {
        this.testingAccount[accountName] = false;
        const msg = err?.error?.detail || 'Lỗi khi test kết nối Facebook!';
        this.msg.error(msg, { nzDuration: 6000 });
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

  // --- SHOPEE AFFILIATE & CATEGORIES METHODS ---

  fetchShopeeCookieStatus(): void {
    this.api.getShopeeCookie().subscribe({
      next: (info) => {
        this.shopeeCookieInfo = info;
      },
      error: () => {}
    });
  }

  openShopeeCookieModal(): void {
    this.shopeeModalVisible = true;
    this.shopeeCookieLoading = true;
    this.shopeeCookieInput = '';
    this.api.getShopeeCookie().subscribe({
      next: (info) => {
        this.shopeeCookieInfo = info;
        this.shopeeCookieInput = info.raw_content || '';
        this.shopeeCookieLoading = false;
      },
      error: () => {
        this.shopeeCookieLoading = false;
      }
    });
  }

  closeShopeeCookieModal(): void {
    this.shopeeModalVisible = false;
    this.shopeeCookieInput = '';
  }

  saveShopeeCookie(): void {
    if (!this.shopeeCookieInput.trim()) {
      this.msg.warning('Vui lòng nhập hoặc dán nội dung Cookie Shopee!');
      return;
    }
    this.shopeeCookieSaving = true;
    this.api.saveShopeeCookie(this.shopeeCookieInput).subscribe({
      next: (res) => {
        this.shopeeCookieSaving = false;
        this.msg.success(res.message);
        if (res.info) {
          this.shopeeCookieInfo = res.info;
        }
        this.shopeeModalVisible = false;
        this.fetchShopeeCookieStatus();
      },
      error: (err) => {
        this.shopeeCookieSaving = false;
        const errMsg = err?.error?.detail || 'Lỗi khi lưu cookie Shopee! Hãy kiểm tra định dạng.';
        this.msg.error(errMsg);
      }
    });
  }

  deleteShopeeCookie(): void {
    if (!confirm('Bạn có chắc muốn xóa file cookie Shopee Affiliate?')) {
      return;
    }
    this.api.deleteShopeeCookie().subscribe({
      next: (res) => {
        this.msg.info(res.message);
        this.shopeeCookieInput = '';
        this.fetchShopeeCookieStatus();
        this.closeShopeeCookieModal();
      },
      error: () => {
        this.msg.error('Lỗi khi xóa cookie Shopee!');
      }
    });
  }

  testShopeeConnect(): void {
    this.testingShopee = true;
    this.api.testShopeeConnect().subscribe({
      next: (res) => {
        this.testingShopee = false;
        if (res.success) {
          this.msg.success(res.message, { nzDuration: 6000 });
        } else {
          this.msg.warning(res.message, { nzDuration: 8000 });
        }
      },
      error: (err) => {
        this.testingShopee = false;
        const msg = err?.error?.detail || 'Lỗi khi test kết nối Shopee!';
        this.msg.error(msg, { nzDuration: 6000 });
      }
    });
  }

  openCategoriesModal(): void {
    this.categoriesModalVisible = true;
    this.categoriesLoading = true;
    this.selectedCategories = {};
    if (this.config && this.config.niches) {
      for (const n of this.config.niches) {
        this.selectedCategories[n] = true;
      }
    }

    this.api.getShopeeCategories().subscribe({
      next: (res) => {
        this.shopeeCategories = res.categories || [];
        this.categoriesLoading = false;
      },
      error: () => {
        this.categoriesLoading = false;
        this.msg.error('Lỗi khi cào danh mục ngành hàng Shopee!');
      }
    });
  }

  closeCategoriesModal(): void {
    this.categoriesModalVisible = false;
  }

  toggleCategory(name: string): void {
    this.selectedCategories[name] = !this.selectedCategories[name];
  }

  selectAllCategories(): void {
    for (const c of this.shopeeCategories) {
      this.selectedCategories[c.name] = true;
    }
  }

  deselectAllCategories(): void {
    this.selectedCategories = {};
  }

  syncCategoriesToNiches(): void {
    const chosen = Object.keys(this.selectedCategories).filter(k => this.selectedCategories[k]);
    if (chosen.length === 0) {
      this.msg.warning('Vui lòng chọn ít nhất 1 ngành hàng để đồng bộ!');
      return;
    }

    this.syncingCategories = true;
    this.api.syncShopeeNiches(chosen).subscribe({
      next: (res) => {
        this.syncingCategories = false;
        this.msg.success(res.message);
        if (this.config) {
          this.config.niches = res.niches;
        }
        this.categoriesModalVisible = false;
      },
      error: () => {
        this.syncingCategories = false;
        this.msg.error('Lỗi khi đồng bộ ngành hàng!');
      }
    });
  }

  onShopeeFileUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        this.shopeeCookieInput = text;
        this.msg.success(`Đã tải nội dung file "${file.name}"!`);
      };
      reader.readAsText(file);
    }
  }

  formatShopeeJson(): void {
    try {
      const obj = JSON.parse(this.shopeeCookieInput);
      this.shopeeCookieInput = JSON.stringify(obj, null, 2);
      this.msg.success('Đã căn chỉnh định dạng JSON!');
    } catch {
      this.msg.warning('Nội dung không phải là cú pháp JSON hợp lệ.');
    }
  }
}

