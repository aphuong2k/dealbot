import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

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
  kind: 'niche' | 'dealhunt';
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

  constructor(private http: HttpClient) {}

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

  runFullPipeline(): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipeline/run-all`, {});
  }

  getGroups(status?: string, kind?: string, search?: string, account?: string): Observable<GroupItem[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (kind) params = params.set('kind', kind);
    if (search) params = params.set('search', search);
    if (account) params = params.set('account', account);
    return this.http.get<GroupItem[]>(`${this.baseUrl}/groups`, { params });
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
