import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject, tap } from 'rxjs';

export interface BotStats {
  deals: { total: number; new: number };
  groups: { total: number; active: number; candidate: number; cooling_down: number };
  posts_today: { total: number; done: number; queued: number; pending_approval: number; failed: number; skipped: number };
  accounts: Array<{
    name: string;
    status: string;
    paused_hours_left: number;
    posts_today: number;
    max_posts_day: number;
    last_warmup_at: number;
  }>;
  dry_run: boolean;
  top_deals: any[];
}

export interface DealItem {
  id: string;
  niche: string;
  title: string;
  price: number;
  orig_price: number;
  discount: number;
  commission: number;
  rating: number;
  sold: number;
  url: string;
  aff_url: string;
  image: string;
  image_path?: string;
  score: number;
  status: string;
  is_valid: number;
  created_at: number;
  posted_count?: number;
  last_posted_at?: number;
  posts_done_count?: number;
  latest_post_url?: string;
  latest_group_name?: string;
  is_vip?: number;
  is_mall?: number;
  brand?: string;
}

export interface SaleCampaign {
  id: string;
  type: string;
  title: string;
  description: string;
  slot: string;
  tag: string;
  is_live_now: boolean;
  url: string;
  aff_url: string;
  banner?: string;
}

export interface CleanupDealsResult {
  success: boolean;
  total_checked: number;
  still_valid_count: number;
  removed_count: number;
  removed_deals: Array<{ id: string; title: string; reason: string }>;
  message: string;
}

export interface GroupItem {
  url: string;
  name: string;
  niche: string;
  members: number;
  posts_per_day?: number;
  activity_text?: string;
  privacy?: string;
  status: 'candidate' | 'joined' | 'approved' | 'banned' | 'cooling_down' | 'skip';
  allow_link: number;
  account: string;
  last_posted_at: number;
  fail_count: number;
  success_count: number;
  consecutive_fails: number;
  priority_score: number;
  last_error?: string;
  kind: 'niche' | 'dealhunt';
  target_type?: 'posting' | 'lazada_hunter';
}

export interface PostItem {
  id: number;
  deal_id: string;
  group_url: string;
  group_name?: string;
  account: string;
  caption: string;
  comment: string;
  image_path: string;
  kind: string;
  status: string;
  sub_id: string;
  comment_status: string;
  comment_retry_at: number;
  comment_retries: number;
  scheduled_at: number;
  posted_at: number;
  post_url?: string;
  error?: string;
}

export interface GradualPostingState {
  is_running: boolean;
  total_target: number;
  completed: number;
  current_group: string;
  current_deal: string;
  current_account: string;
  next_post_time: string | null;
  remaining_delay: number;
  delay_seconds: number;
  status: string;
  last_result?: any;
  history: any[];
}

export interface StartGradualPostPayload {
  group_urls?: string[];
  delay_seconds?: number;
  account?: string;
  dry_run?: boolean;
  link_in_comment?: boolean;
}

export interface SingleGroupPostPayload {
  group_url: string;
  deal_id?: string;
  account?: string;
  dry_run?: boolean;
  custom_caption?: string;
  link_in_comment?: boolean;
}

export interface CouponItem {
  id: string;
  merchant: string;
  title: string;
  code: string;
  detail: string;
  category?: string;
  save_url?: string;
  start_at: number;
  end_at: number;
  url: string;
  aff_url: string;
  used: number;
}

export interface EventItem {
  title: string;
  merchant: string;
  start: string;
  end: string;
  detail: string;
  link: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8000/api';

  private initialTasksStatus: TasksStatus = {
    pipeline: {
      is_running: false,
      step: 0,
      step_name: '',
      started_at: 0,
      elapsed_seconds: 0,
      deals_added: 0,
      deals_updated: 0,
      posts_planned: 0,
      posts_done: 0,
      message: 'Sẵn sàng',
      last_finished_at: 0,
      last_result: null
    },
    lazada_hunter: {
      is_running: false,
      trigger_type: 'none',
      started_at: 0,
      elapsed_seconds: 0,
      total_products: 0,
      current_index: 0,
      current_product_name: '',
      deals_found: 0,
      message: 'Sẵn sàng',
      last_finished_at: 0,
      last_result: null
    },
    lazada_general: {
      is_running: false,
      started_at: 0,
      elapsed_seconds: 0,
      current_category: '',
      current_keyword: '',
      total_keywords: 0,
      current_index: 0,
      items_scanned: 0,
      deals_found: 0,
      message: 'Sẵn sàng',
      last_finished_at: 0,
      last_result: null
    },
    lazada_tmall: {
      is_running: false,
      trigger_type: 'none',
      started_at: 0,
      elapsed_seconds: 0,
      current_category_name: '',
      current_shop_name: '',
      current_shop_index: 0,
      total_shops: 0,
      items_scanned: 0,
      deals_found: 0,
      message: 'Sẵn sàng',
      last_finished_at: 0,
      last_result: null
    }
  };

  private tasksStatusSubject = new BehaviorSubject<TasksStatus>(this.initialTasksStatus);
  public tasksStatus$ = this.tasksStatusSubject.asObservable();
  private isPolling = false;

  constructor(private http: HttpClient) {
    this.startTasksPolling();
  }

  public startTasksPolling(): void {
    if (this.isPolling) return;
    this.isPolling = true;

    const poll = () => {
      this.getTasksStatus().subscribe({
        next: (status) => {
          this.tasksStatusSubject.next(status);
          const nextInterval = (status.pipeline?.is_running || status.lazada_hunter?.is_running || status.lazada_general?.is_running || status.lazada_tmall?.is_running) ? 1500 : 4000;
          setTimeout(poll, nextInterval);
        },
        error: () => {
          setTimeout(poll, 6000);
        }
      });
    };
    poll();
  }

  public refreshTasksStatusNow(): void {
    this.getTasksStatus().subscribe({
      next: (status) => this.tasksStatusSubject.next(status),
      error: () => {}
    });
  }

  getTasksStatus(): Observable<TasksStatus> {
    return this.http.get<TasksStatus>(`${this.baseUrl}/tasks/status`);
  }

  getPipelineStatus(): Observable<PipelineStatus> {
    return this.http.get<PipelineStatus>(`${this.baseUrl}/pipeline/status`);
  }

  getPipelineConfig(): Observable<PipelineAutoConfig> {
    return this.http.get<PipelineAutoConfig>(`${this.baseUrl}/pipeline/config`);
  }

  updatePipelineConfig(payload: Partial<PipelineAutoConfig>): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipeline/config`, payload);
  }

  getLazadaHunterStatus(): Observable<LazadaHunterStatus> {
    return this.http.get<LazadaHunterStatus>(`${this.baseUrl}/lazada/hunter-status`);
  }

  getStats(): Observable<BotStats> {
    return this.http.get<BotStats>(`${this.baseUrl}/stats`);
  }

  getDeals(niche?: string, status?: string, search?: string, isVip?: boolean, isMall?: boolean): Observable<DealItem[]> {
    let params = new HttpParams();
    if (niche) params = params.set('niche', niche);
    if (status) params = params.set('status', status);
    if (search) params = params.set('search', search);
    if (isVip !== undefined && isVip !== null) params = params.set('is_vip', isVip ? 'true' : 'false');
    if (isMall !== undefined && isMall !== null) params = params.set('is_mall', isMall ? 'true' : 'false');
    return this.http.get<DealItem[]>(`${this.baseUrl}/deals`, { params });
  }

  getVipDeals(limit: number = 40): Observable<DealItem[]> {
    return this.http.get<DealItem[]>(`${this.baseUrl}/deals/vip?limit=${limit}`);
  }

  crawlDeals(niche?: string): Observable<any> {
    let params = new HttpParams();
    if (niche) params = params.set('niche', niche);
    return this.http.post(`${this.baseUrl}/deals/crawl`, { niche }, { params });
  }

  cleanupExpiredDeals(deleteFromDb: boolean = true): Observable<CleanupDealsResult> {
    return this.http.post<CleanupDealsResult>(`${this.baseUrl}/deals/cleanup`, { delete_from_db: deleteFromDb });
  }

  deleteDeal(id: string | number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/deals/${id}`);
  }

  clearAllDeals(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/deals`);
  }

  runFullPipeline(): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipeline/run-all`, {}).pipe(
      tap(() => this.refreshTasksStatusNow())
    );
  }

  getGroups(status?: string, kind?: string, search?: string, account?: string, target_type?: string): Observable<GroupItem[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (kind) params = params.set('kind', kind);
    if (search) params = params.set('search', search);
    if (account) params = params.set('account', account);
    if (target_type) params = params.set('target_type', target_type);
    return this.http.get<GroupItem[]>(`${this.baseUrl}/groups`, { params });
  }

  getLazadaHunterGroups(): Observable<GroupItem[]> {
    return this.http.get<GroupItem[]>(`${this.baseUrl}/lazada/hunter-groups`);
  }

  addLazadaHunterGroup(url: string, name?: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/hunter-groups`, { url, name });
  }

  removeLazadaHunterGroup(url: string): Observable<any> {
    let params = new HttpParams().set('url', url);
    return this.http.delete(`${this.baseUrl}/lazada/hunter-groups`, { params });
  }

  updateGroup(url: string, data: Partial<GroupItem>): Observable<any> {
    let params = new HttpParams().set('url', url);
    return this.http.put(`${this.baseUrl}/groups`, data, { params });
  }

  discoverGroups(): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/discover`, {});
  }

  getPosts(status?: string, account?: string): Observable<PostItem[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (account) params = params.set('account', account);
    return this.http.get<PostItem[]>(`${this.baseUrl}/posts`, { params });
  }

  runSinglePost(postId: number): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts/${postId}/run-now`, {});
  }

  planPosts(): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts/plan`, {});
  }

  runDuePosts(): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts/run-due`, {});
  }

  getPostsHistory(account?: string, limit: number = 50): Observable<PostItem[]> {
    let params = new HttpParams();
    if (account) params = params.set('account', account);
    params = params.set('limit', limit.toString());
    return this.http.get<PostItem[]>(`${this.baseUrl}/posts/history`, { params });
  }

  clearPostsHistory(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/posts/history`);
  }

  deletePost(postId: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/posts/${postId}`);
  }

  getGradualPostingStatus(): Observable<GradualPostingState> {
    return this.http.get<GradualPostingState>(`${this.baseUrl}/posts/gradual-status`);
  }

  startGradualPosting(payload: StartGradualPostPayload): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/posts/start-gradual`, payload);
  }

  stopGradualPosting(): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/posts/stop-gradual`, {});
  }

  postSingleGroup(payload: SingleGroupPostPayload): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/groups/post-single`, payload);
  }

  getGroupMatchedDeals(): Observable<{ [url: string]: any }> {
    return this.http.get<{ [url: string]: any }>(`${this.baseUrl}/groups/matched-deals`);
  }


  getCoupons(category?: string): Observable<CouponItem[]> {
    let params = new HttpParams();
    if (category) params = params.set('category', category);
    return this.http.get<CouponItem[]>(`${this.baseUrl}/coupons`, { params });
  }

  getDailyCampaigns(): Observable<SaleCampaign[]> {
    return this.http.get<SaleCampaign[]>(`${this.baseUrl}/coupons/campaigns`);
  }

  refreshCoupons(): Observable<any> {
    return this.http.post(`${this.baseUrl}/coupons/refresh`, {});
  }

  getEvents(): Observable<EventItem[]> {
    return this.http.get<EventItem[]>(`${this.baseUrl}/events`);
  }

  saveEvents(events: EventItem[]): Observable<any> {
    return this.http.post(`${this.baseUrl}/events`, events);
  }

  getConfig(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/config`);
  }

  updateConfig(cfg: any): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}/config`, cfg);
  }

  warmupAccounts(): Observable<any> {
    return this.http.post(`${this.baseUrl}/accounts/warmup`, {});
  }

  testTelegramNotify(): Observable<any> {
    return this.http.post(`${this.baseUrl}/telegram/test-notify`, {});
  }

  postDigestTelegram(): Observable<any> {
    return this.http.post(`${this.baseUrl}/telegram/post-digest`, {});
  }

  getAccountsCookies(): Observable<AccountCookieInfo[]> {
    return this.http.get<AccountCookieInfo[]>(`${this.baseUrl}/accounts/cookies`);
  }

  getAccountCookie(accountName: string): Observable<AccountCookieInfo> {
    return this.http.get<AccountCookieInfo>(`${this.baseUrl}/accounts/${accountName}/cookie`);
  }

  saveAccountCookie(accountName: string, cookieData: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/accounts/${accountName}/cookie`, { cookie_data: cookieData });
  }

  deleteAccountCookie(accountName: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/accounts/${accountName}/cookie`);
  }

  testFacebookConnect(accountName: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/accounts/${accountName}/test-connect`, {});
  }

  // --- SHOPEE AFFILIATE & CATEGORIES ---
  getShopeeCookie(): Observable<ShopeeCookieInfo> {
    return this.http.get<ShopeeCookieInfo>(`${this.baseUrl}/shopee/cookie`);
  }

  saveShopeeCookie(cookieData: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/shopee/cookie`, { cookie_data: cookieData });
  }

  deleteShopeeCookie(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/shopee/cookie`);
  }

  testShopeeConnect(): Observable<any> {
    return this.http.post(`${this.baseUrl}/shopee/test-connect`, {});
  }

  getShopeeCategories(): Observable<{ categories: ShopeeCategory[]; total: number }> {
    return this.http.get<{ categories: ShopeeCategory[]; total: number }>(`${this.baseUrl}/shopee/categories`);
  }

  syncShopeeNiches(niches: string[]): Observable<any> {
    return this.http.post(`${this.baseUrl}/shopee/sync-niches`, { niches });
  }

  // --- SHOPEE AFFILIATE PORTAL & OPEN API CONVERTER ---
  getShopeeAffPortalCookie(): Observable<ShopeeCookieInfo> {
    return this.http.get<ShopeeCookieInfo>(`${this.baseUrl}/shopee/affiliate-portal-cookie`);
  }

  saveShopeeAffPortalCookie(cookieData: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/shopee/affiliate-portal-cookie`, { cookie_data: cookieData });
  }

  deleteShopeeAffPortalCookie(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/shopee/affiliate-portal-cookie`);
  }

  getShopeeOpenApiConfig(): Observable<{ app_id: string; secret: string }> {
    return this.http.get<{ app_id: string; secret: string }>(`${this.baseUrl}/shopee/open-api-config`);
  }

  saveShopeeOpenApiConfig(appId: string, secret: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/shopee/open-api-config`, { app_id: appId, secret });
  }

  testConvertShopeeLink(url: string, subIds?: string[]): Observable<{
    success: boolean;
    short_link?: string;
    full_tracking_link?: string;
    affiliate_id?: string;
    affiliate_name?: string;
    method?: string;
    message: string;
  }> {
    return this.http.post<{
      success: boolean;
      short_link?: string;
      full_tracking_link?: string;
      affiliate_id?: string;
      affiliate_name?: string;
      method?: string;
      message: string;
    }>(`${this.baseUrl}/shopee/test-convert`, { url, sub_ids: subIds });
  }


  // --- FACEBOOK GROUP SCANNER ---
  scanJoinedGroups(accountName: string): Observable<ScanGroupsResult> {
    return this.http.post<ScanGroupsResult>(`${this.baseUrl}/accounts/${accountName}/scan-groups`, {});
  }

  leaveGroup(accountName: string, groupUrl: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/accounts/${accountName}/leave-group`, { group_url: groupUrl });
  }

  removeGroupFromDb(url: string): Observable<any> {
    let params = new HttpParams().set('url', url);
    return this.http.delete(`${this.baseUrl}/groups/remove`, { params });
  }

  importScannedGroups(groups: Array<{
    url: string;
    name?: string;
    account?: string;
    status?: string;
    niche?: string;
    kind?: string;
    members?: number;
    posts_per_day?: number;
    activity_text?: string;
    privacy?: string;
    priority_score?: number;
  }>): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/import-scanned`, { groups });
  }

  testPost(payload: TestPostPayload): Observable<TestPostResult> {
    return this.http.post<TestPostResult>(`${this.baseUrl}/posts/test`, payload);
  }

  joinGroup(account: string, groupUrl: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/accounts/${account}/join-group`, { group_url: groupUrl });
  }

  autoJoinBatch(account: string, limit: number = 5, groupUrls?: string[]): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/auto-join-batch`, {
      account,
      limit,
      group_urls: groupUrls
    });
  }

  searchNicheGroups(payload: SearchNicheGroupsPayload): Observable<SearchNicheGroupsResult> {
    return this.http.post<SearchNicheGroupsResult>(`${this.baseUrl}/groups/search-niche`, payload);
  }

  // --- FACEBOOK GROUP BLACKLIST & AUTO-LEAVE ---
  getBlacklistedGroups(): Observable<GroupItem[]> {
    return this.http.get<GroupItem[]>(`${this.baseUrl}/groups/blacklist`);
  }

  getBlacklistCandidates(maxConsecutiveFails: number = 3, maxPendingCount: number = 2): Observable<any[]> {
    let params = new HttpParams()
      .set('max_consecutive_fails', maxConsecutiveFails.toString())
      .set('max_pending_count', maxPendingCount.toString());
    return this.http.get<any[]>(`${this.baseUrl}/groups/blacklist/candidates`, { params });
  }

  scanAndCleanBlacklist(payload: { auto_leave_fb?: boolean; max_groups?: number }): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/blacklist/scan-and-clean`, payload);
  }

  banGroupManual(groupUrl: string, reason?: string, autoLeaveFb: boolean = true, account?: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/blacklist/ban`, {
      group_url: groupUrl,
      reason: reason || 'Chặn và rời nhóm thủ công bởi người dùng',
      auto_leave_fb: autoLeaveFb,
      account: account || undefined
    });
  }

  unbanGroup(groupUrl: string, newStatus: string = 'candidate'): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/blacklist/unban`, {
      group_url: groupUrl,
      new_status: newStatus
    });
  }

  getBlacklistConfig(): Observable<any> {
    return this.http.get(`${this.baseUrl}/groups/blacklist/config`);
  }

  saveBlacklistConfig(config: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/blacklist/config`, config);
  }

  // --- LAZADA DEAL HUNTER ---
  getLazadaCookie(): Observable<LazadaCookieInfo> {
    return this.http.get<LazadaCookieInfo>(`${this.baseUrl}/lazada/cookie`);
  }

  saveLazadaCookie(cookieData: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/cookie`, { cookie_data: cookieData });
  }

  testLazadaCookie(): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/cookie/test`, {});
  }

  getLazadaHunterConfig(): Observable<LazadaHunterConfig> {
    return this.http.get<LazadaHunterConfig>(`${this.baseUrl}/lazada/config`);
  }

  updateLazadaHunterConfig(config: Partial<LazadaHunterConfig>): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/config`, config);
  }

  getLazadaTrackedProducts(): Observable<LazadaTrackedProduct[]> {
    return this.http.get<LazadaTrackedProduct[]>(`${this.baseUrl}/lazada/products`);
  }

  createLazadaTrackedProduct(product: Partial<LazadaTrackedProduct>): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/products`, product);
  }

  updateLazadaTrackedProduct(id: number, product: Partial<LazadaTrackedProduct>): Observable<any> {
    return this.http.put(`${this.baseUrl}/lazada/products/${id}`, product);
  }

  deleteLazadaTrackedProduct(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/products/${id}`);
  }

  toggleLazadaTrackedProduct(id: number): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/products/${id}/toggle`, {});
  }

  triggerScanFbMarket(groupUrls: string[], account?: string, postsPerGroup: number = 50): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/scan-fb`, { group_urls: groupUrls, account: account || 'nick_a', posts_per_group: postsPerGroup });
  }

  getScanFbMarketStatus(): Observable<any> {
    return this.http.get(`${this.baseUrl}/lazada/scan-fb/status`);
  }

  getLazadaDeals(limit: number = 50): Observable<LazadaFoundDeal[]> {
    return this.http.get<LazadaFoundDeal[]>(`${this.baseUrl}/lazada/deals?limit=${limit}`);
  }

  runLazadaHunterNow(): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/run-hunter-now`, {}).pipe(
      tap(() => this.refreshTasksStatusNow())
    );
  }

  testSearchLazada(keyword: string, filterMallOnly: boolean = true): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/test-search`, { keyword, filter_mall_only: filterMallOnly });
  }

  cleanupJunkLazadaProducts(): Observable<{ success: boolean; message: string; deleted: number }> {
    return this.http.post<{ success: boolean; message: string; deleted: number }>(`${this.baseUrl}/lazada/products/cleanup-junk`, {});
  }

  getLazadaHunterLogs(limit: number = 50): Observable<LazadaHunterLog[]> {
    return this.http.get<LazadaHunterLog[]>(`${this.baseUrl}/lazada/logs?limit=${limit}`);
  }

  clearLazadaHunterLogs(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/logs`);
  }

  getDeepDrops(category?: string, limit: number = 50, offset: number = 0): Observable<DeepDropDeal[]> {
    let params: any = { limit, offset };
    if (category) params.category = category;
    return this.http.get<DeepDropDeal[]>(`${this.baseUrl}/lazada/deep-drops`, { params });
  }

  getDeepDropsStatus(): Observable<LazadaGeneralStatus> {
    return this.http.get<LazadaGeneralStatus>(`${this.baseUrl}/lazada/deep-drops/status`);
  }

  triggerDeepDropsScan(payload?: { categories?: string[]; min_drop_pct?: number }): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/lazada/deep-drops/scan`, payload || {}).pipe(
      tap(() => this.refreshTasksStatusNow())
    );
  }

  clearDeepDrops(): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}/lazada/deep-drops`);
  }

  getDeepDropsLogs(limit: number = 30): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/lazada/deep-drops/logs`, { params: { limit } });
  }

  deleteLazadaDeal(dealId: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/deals/${dealId}`);
  }

  clearLazadaDeals(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/deals`);
  }

  deleteDeepDrop(dropId: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/deep-drops/${dropId}`);
  }

  clearDeepDropsLogs(): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/deep-drops/logs`);
  }

  getDeepDropsConfig(): Observable<any> {
    return this.http.get(`${this.baseUrl}/lazada/deep-drops/config`);
  }

  updateDeepDropsConfig(cfg: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/deep-drops/config`, cfg);
  }

  getRadarCategories(activeOnly: boolean = false): Observable<RadarCategoriesResponse> {
    return this.http.get<RadarCategoriesResponse>(`${this.baseUrl}/lazada/categories`, { params: { active_only: activeOnly } });
  }

  saveRadarCategory(payload: RadarCategoryItem): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/categories`, payload);
  }

  deleteRadarCategory(catId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/lazada/categories/${catId}`);
  }

  syncLazadaCategories(): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/categories/sync`, {});
  }

  resetRadarCategories(): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/categories/reset-default`, {});
  }

  // --- TMALL BRAND DIRECTORY & SHOP SCANNER ---
  getTmallCategories(activeOnly: boolean = false): Observable<{ categories: TmallCategoryItem[]; total_categories: number; active_categories: number }> {
    return this.http.get<{ categories: TmallCategoryItem[]; total_categories: number; active_categories: number }>(
      `${this.baseUrl}/lazada/tmall/categories`,
      { params: { active_only: activeOnly } }
    );
  }

  toggleTmallCategory(categoryId: string, isActive: boolean): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/tmall/categories/toggle`, {
      category_id: categoryId,
      is_active: isActive
    });
  }

  getTmallShops(categoryId?: string, activeOnly: boolean = false, limit: number = 300): Observable<{ shops: TmallShopItem[]; total: number }> {
    let params: any = { active_only: activeOnly, limit };
    if (categoryId) params.category_id = categoryId;
    return this.http.get<{ shops: TmallShopItem[]; total: number }>(`${this.baseUrl}/lazada/tmall/shops`, { params });
  }

  syncTmallBrands(): Observable<any> {
    return this.http.post(`${this.baseUrl}/lazada/tmall/sync-brands`, {});
  }

  getTmallScanStatus(): Observable<LazadaTmallStatus> {
    return this.http.get<LazadaTmallStatus>(`${this.baseUrl}/lazada/tmall/status`);
  }

  triggerTmallBrandScan(payload?: { categories?: string[]; min_drop_pct?: number; batch_shops?: number; max_pages?: number }): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/lazada/tmall/scan`, payload || {}).pipe(
      tap(() => this.refreshTasksStatusNow())
    );
  }

  startTmallContinuousScan(payload?: { categories?: string[]; min_drop_pct?: number; max_pages?: number }): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/lazada/tmall/continuous/start`, payload || {}).pipe(
      tap(() => this.refreshTasksStatusNow())
    );
  }

  stopTmallContinuousScan(): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/lazada/tmall/continuous/stop`, {}).pipe(
      tap(() => this.refreshTasksStatusNow())
    );
  }
}

export interface RadarCategoryItem {
  id: string;
  name: string;
  icon?: string;
  keywords: string[];
  keywords_count?: number;
  is_active?: boolean;
  sort_order?: number;
}

export interface RadarCategoriesResponse {
  categories: RadarCategoryItem[];
  total_categories: number;
  total_keywords: number;
}

export interface TestPostPayload {
  account: string;
  group_url: string;
  caption: string;
  comment?: string;
  dry_run: boolean;
  image_path?: string;
}

export interface TestPostResult {
  success: boolean;
  status: string;
  comment_status: string;
  post_url?: string;
  dry_run: boolean;
  message: string;
}


export interface AccountCookieInfo {
  account: string;
  cookie_file: string;
  exists: boolean;
  count: number;
  c_user?: string | null;
  has_xs: boolean;
  updated_at?: number | null;
  size_bytes: number;
  raw_content?: string;
}

export interface ShopeeCookieInfo {
  exists: boolean;
  count: number;
  file_name?: string;
  spc_u?: string | null;
  affiliate_id?: string | null;
  affiliate_name?: string | null;
  email?: string | null;
  has_spc_ec: boolean;
  has_aff_session?: boolean;
  updated_at?: number | null;
  size_bytes: number;
  raw_content?: string;
}

export interface ShopeeCategory {
  catid: number;
  name: string;
  english_name?: string;
  children?: Array<{ catid: number; name: string }>;
}

export interface ScannedGroup {
  url: string;
  name: string;
  slug: string;
  niche?: string;
  kind?: string;
}

export interface EvaluatedGroup {
  url: string;
  name: string;
  slug: string;
  niche: string;
  kind: 'niche' | 'dealhunt';
  members: number;
  posts_per_day: number;
  privacy: 'public' | 'private';
  activity_text: string;
  status: string;
  is_qualified: boolean;
  evaluation_note: string;
  priority_score: number;
  join_message?: string;
}

export interface SearchNicheGroupsPayload {
  account: string;
  keyword: string;
  niche?: string;
  min_members?: number;
  min_posts_per_day?: number;
  only_public?: boolean;
  auto_join?: boolean;
  max_results?: number;
  max_scroll?: number;
}

export interface SearchNicheGroupsResult {
  success: boolean;
  message: string;
  keyword: string;
  niche: string;
  groups: EvaluatedGroup[];
  qualified_count: number;
  account?: string;
}

export interface ScanGroupsResult {
  success: boolean;
  message: string;
  account?: string;
  groups: ScannedGroup[];
}

export interface LazadaCookieInfo {
  exists: boolean;
  count: number;
  user_name: string | null;
  updated_at: number | null;
  size_bytes: number;
  is_valid: boolean;
  raw_preview: string;
}

export interface LazadaHunterConfig {
  enabled: boolean;
  interval_minutes: number;
  filter_mall_only: boolean;
  min_discount_pct: number;
  selected_groups: string[];
  max_search_results: number;
}

export interface LazadaTrackedProduct {
  id: number;
  name: string;
  clean_keyword: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  sample_count: number;
  source_groups: string;
  is_active: number;
  filter_mall_only: number;
  min_discount_pct: number;
  last_scanned_at: number;
  created_at: number;
  updated_at: number;
}

export interface LazadaFoundDeal {
  id: number;
  product_id: number;
  product_name: string;
  laz_item_id: string;
  laz_sku_id: string;
  variation_name: string;
  seller_name: string;
  is_mall: number;
  laz_price: number;
  market_avg_price: number;
  diff_pct: number;
  product_url: string;
  image_url: string;
  sent_to_tg: number;
  sent_to_tg_at: number;
  created_at: number;
}

export interface LazadaHunterLog {
  id: number;
  started_at: number;
  finished_at: number;
  status: 'success' | 'running' | 'skipped' | 'error';
  trigger_type: 'auto_5m' | 'manual';
  products_scanned: number;
  deals_found: number;
  telegram_sent: number;
  details: string;
  details_parsed?: any[];
  message: string;
  created_at: number;
}

export interface PipelineStatus {
  is_running: boolean;
  step: number; // 0: idle, 1: crawling, 2: planning, 3: posting, 4: done
  step_name: string;
  started_at: number;
  elapsed_seconds: number;
  deals_added: number;
  deals_updated: number;
  posts_planned: number;
  posts_done: number;
  message: string;
  last_finished_at: number;
  last_result: string | null;
  error?: string | null;
  auto_enabled?: boolean;
  interval_hours?: number;
  next_run_at?: number;
}

export interface PipelineAutoConfig {
  enabled: boolean;
  interval_hours: number;
  auto_post_due: boolean;
  last_run_at?: number;
  next_run_at?: number;
}

export interface LazadaHunterStatus {
  is_running: boolean;
  trigger_type: string;
  started_at: number;
  elapsed_seconds: number;
  total_products: number;
  current_index: number;
  current_product_name: string;
  deals_found: number;
  message: string;
  last_finished_at: number;
  last_result: string | null;
}

export interface LazadaGeneralStatus {
  is_running: boolean;
  started_at: number;
  elapsed_seconds: number;
  current_category: string;
  current_keyword: string;
  total_keywords: number;
  current_index: number;
  items_scanned: number;
  deals_found: number;
  message: string;
  last_finished_at: number;
  last_result: string | null;
}

export interface DeepDropDeal {
  id: number;
  item_id: string;
  sku_id: string;
  product_title: string;
  category: string;
  variation_name: string;
  sibling_count: number;
  sibling_avg_price: number;
  drop_price: number;
  drop_pct: number;
  stock: number;
  seller_name: string;
  is_mall: number;
  product_url: string;
  image_url: string;
  sent_to_tg: number;
  sent_to_tg_at: number;
  created_at: number;
}

export interface TmallCategoryItem {
  id: string;
  name: string;
  icon?: string;
  is_active: number;
  sort_order: number;
  shops_count: number;
  deals_count: number;
  updated_at?: number;
}

export interface TmallShopItem {
  id: number;
  category_id: string;
  category_name: string;
  shop_name: string;
  shop_slug: string;
  shop_url: string;
  logo_url?: string;
  is_active: number;
  total_products_scanned: number;
  last_scanned_at?: number;
}

export interface LazadaTmallStatus {
  is_running: boolean;
  continuous_mode?: boolean;
  current_loop?: number;
  trigger_type?: string;
  started_at: number;
  elapsed_seconds: number;
  current_category_name: string;
  current_shop_name: string;
  current_shop_index: number;
  total_shops: number;
  items_scanned: number;
  deals_found: number;
  message: string;
  last_finished_at?: number;
  last_result?: string | null;
}

export interface TasksStatus {
  pipeline: PipelineStatus;
  lazada_hunter: LazadaHunterStatus;
  lazada_general?: LazadaGeneralStatus;
  lazada_tmall?: LazadaTmallStatus;
}
